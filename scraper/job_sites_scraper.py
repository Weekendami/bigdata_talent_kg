import argparse
import csv
import html as html_lib
import json
import os
import random
import re
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from urllib.parse import quote_plus

from lxml import html
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_OUTPUT = os.path.join(DATA_DIR, "job_sites.csv")


@dataclass
class JobRecord:
    title: str
    company: str
    location: str
    salary: str
    experience: str
    degree: str
    tags: str
    job_description: str
    job_url: str
    source: str
    scraped_at: str


@dataclass(frozen=True)
class XPathSiteSpec:
    list_wait_xpath: str
    card_xpath: str
    title_xpath: str
    company_xpath: str
    location_xpath: str
    salary_xpath: str
    experience_xpath: str
    degree_xpath: str
    tags_xpath: str
    summary_xpath: str
    link_xpath: str
    detail_wait_xpath: str
    detail_title_xpath: str
    detail_company_xpath: str
    detail_location_xpath: str
    detail_salary_xpath: str
    detail_experience_xpath: str
    detail_degree_xpath: str
    detail_tags_xpath: str
    detail_description_xpath: str


def _clean(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _normalize_url(url: str, site: str) -> str:
    value = _clean(url)
    if not value:
        return ""
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("/"):
        host = "https://www.zhaopin.com" if site == "zhaopin" else "https://www.51job.com"
        return f"{host}{value}"
    return value


def _extract_first(node, xpath: str) -> str:
    values = node.xpath(xpath)
    for value in values:
        text = _clean(value)
        if text:
            return text
    return ""


def _extract_joined(node, xpath: str) -> str:
    values = [_clean(item) for item in node.xpath(xpath)]
    values = [item for item in values if item]
    return "|".join(dict.fromkeys(values))


def _extract_with_regex(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        value = html_lib.unescape(match.group(1))
        value = value.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t").replace("\\/", "/")
        value = _clean(value)
        if value:
            return value
    return ""


def _chunk_pages(total_pages: int, worker_count: int) -> list[list[int]]:
    chunks = [[] for _ in range(worker_count)]
    for idx, page_no in enumerate(range(1, total_pages + 1)):
        chunks[idx % worker_count].append(page_no)
    return [chunk for chunk in chunks if chunk]


def _chunk_records(rows: list[JobRecord], worker_count: int) -> list[list[JobRecord]]:
    chunks = [[] for _ in range(worker_count)]
    for idx, row in enumerate(rows):
        chunks[idx % worker_count].append(row)
    return [chunk for chunk in chunks if chunk]


def _dedupe_rows(rows: list[JobRecord]) -> list[JobRecord]:
    seen: set[tuple[str, str, str, str, str]] = set()
    deduped: list[JobRecord] = []
    for row in rows:
        key = (row.source, row.title, row.company, row.location, row.job_url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _create_driver(headless: bool) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,900")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=zh-CN")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


class BaseSiteAdapter(ABC):
    site: str
    spec: XPathSiteSpec

    @abstractmethod
    def build_search_url(self, keyword: str, city: str, page: int) -> str:
        pass

    def wait_for_list_page(self, driver: webdriver.Chrome, timeout: int) -> None:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, self.spec.list_wait_xpath))
        )

    def wait_for_detail_page(self, driver: webdriver.Chrome, timeout: int) -> None:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, self.spec.detail_wait_xpath))
        )

    def parse_list_page(self, page_source: str) -> list[JobRecord]:
        tree = html.fromstring(page_source)
        cards = tree.xpath(self.spec.card_xpath)
        rows: list[JobRecord] = []
        scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for card in cards:
            title = _extract_first(card, self.spec.title_xpath)
            company = _extract_first(card, self.spec.company_xpath)
            location = _extract_first(card, self.spec.location_xpath)
            salary = _extract_first(card, self.spec.salary_xpath)
            experience = _extract_first(card, self.spec.experience_xpath)
            degree = _extract_first(card, self.spec.degree_xpath)
            tags = _extract_joined(card, self.spec.tags_xpath)
            summary = _extract_joined(card, self.spec.summary_xpath)
            job_url = _normalize_url(_extract_first(card, self.spec.link_xpath), self.site)

            if not any([title, company, location, salary, job_url]):
                continue

            rows.append(
                JobRecord(
                    title=title,
                    company=company,
                    location=location,
                    salary=salary,
                    experience=experience,
                    degree=degree,
                    tags=tags,
                    job_description=summary,
                    job_url=job_url,
                    source=self.site,
                    scraped_at=scraped_at,
                )
            )

        return rows

    def parse_detail_page(self, page_source: str, base_row: JobRecord) -> JobRecord:
        tree = html.fromstring(page_source)
        title = _extract_first(tree, self.spec.detail_title_xpath) or base_row.title
        company = _extract_first(tree, self.spec.detail_company_xpath) or base_row.company
        location = _extract_first(tree, self.spec.detail_location_xpath) or base_row.location
        salary = _extract_first(tree, self.spec.detail_salary_xpath) or base_row.salary
        experience = _extract_first(tree, self.spec.detail_experience_xpath) or base_row.experience
        degree = _extract_first(tree, self.spec.detail_degree_xpath) or base_row.degree
        tags = _extract_joined(tree, self.spec.detail_tags_xpath) or base_row.tags
        description = _extract_joined(tree, self.spec.detail_description_xpath) or base_row.job_description

        return JobRecord(
            title=title,
            company=company,
            location=location,
            salary=salary,
            experience=experience,
            degree=degree,
            tags=tags,
            job_description=description,
            job_url=base_row.job_url,
            source=self.site,
            scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def should_enrich_detail(self) -> bool:
        return True


class ZhaopinAdapter(BaseSiteAdapter):
    site = "zhaopin"
    spec = XPathSiteSpec(
        list_wait_xpath=(
            "//div[contains(@class,'positionlist')]"
            " | //div[contains(@class,'joblist-box')]"
            " | //div[contains(@class,'position-card')]"
        ),
        card_xpath=(
            "//div[contains(@class,'positionlist')]/div[contains(@class,'joblist-box__item')]"
            " | //div[contains(@class,'position-card')]"
            " | //div[contains(@class,'joblist-box__item')]"
        ),
        title_xpath=(
            ".//span[contains(@class,'job-title')]//text()"
            " | .//a[contains(@class,'position-card__job-name')]//text()"
            " | .//a[contains(@class,'jobtitle')]//text()"
        ),
        company_xpath=(
            ".//a[contains(@class,'company-name')]//text()"
            " | .//span[contains(@class,'company-name')]//text()"
            " | .//div[contains(@class,'company__title')]//text()"
        ),
        location_xpath=(
            ".//span[contains(@class,'job-area')]//text()"
            " | .//span[contains(@class,'position-card__city')]//text()"
            " | .//li[contains(@class,'job-area')]//text()"
        ),
        salary_xpath=(
            ".//span[contains(@class,'salary')]//text()"
            " | .//p[contains(@class,'salary')]//text()"
            " | .//div[contains(@class,'jobinfo__salary')]//text()"
        ),
        experience_xpath=(
            ".//span[contains(@class,'job-exp')]//text()"
            " | .//li[contains(@class,'working-exp')]//text()"
            " | .//span[contains(@class,'experience')]//text()"
        ),
        degree_xpath=(
            ".//span[contains(@class,'job-education')]//text()"
            " | .//li[contains(@class,'education')]//text()"
            " | .//span[contains(@class,'education')]//text()"
        ),
        tags_xpath=(
            ".//div[contains(@class,'job-welfare')]//text()"
            " | .//div[contains(@class,'welfare__item')]//text()"
            " | .//span[contains(@class,'tag')]//text()"
        ),
        summary_xpath=(
            ".//div[contains(@class,'jobinfo__other-info')]//text()"
            " | .//div[contains(@class,'job-summary')]//text()"
        ),
        link_xpath=(
            ".//a[contains(@href,'jobs.zhaopin.com')][1]/@href"
            " | .//a[contains(@class,'position-card__job-name')][1]/@href"
            " | .//a[1]/@href"
        ),
        detail_wait_xpath="//h1[contains(@class,'summary-plane__title')]",
        detail_title_xpath="//h1[contains(@class,'summary-plane__title')]/text()",
        detail_company_xpath=(
            "//a[contains(@class,'company-name')]/text()"
            " | //div[contains(@class,'company')]/a/text()"
            " | //span[contains(@class,'company-name')]/text()"
        ),
        detail_location_xpath=(
            "//ul[contains(@class,'summary-plane__info')]/li[1]/span/text()"
            " | //ul[contains(@class,'summary-plane__info')]/li[1]/a/text()"
            " | //ul[contains(@class,'summary-plane__info')]/li[1]//text()"
            " | //span[contains(@class,'job-address')]/text()"
            " | //div[contains(@class,'job-address')]//text()"
        ),
        detail_salary_xpath="//span[contains(@class,'summary-plane__salary')]/text()",
        detail_experience_xpath="//ul[contains(@class,'summary-plane__info')]/li[2]//text()",
        detail_degree_xpath="//ul[contains(@class,'summary-plane__info')]/li[3]//text()",
        detail_tags_xpath=(
            "//div[contains(@class,'welfare-tab-box')]//text()"
            " | //span[contains(@class,'highlights__content-item')]/text()"
        ),
        detail_description_xpath=(
            "//div[contains(@class,'describtion__detail-content')]//text()"
            " | //section[contains(@class,'job-detail')]//text()"
            " | //div[contains(@class,'jobdetail-box')]//text()"
        ),
    )

    def build_search_url(self, keyword: str, city: str, page: int) -> str:
        return f"https://sou.zhaopin.com/?jl={quote_plus(city)}&kw={quote_plus(keyword)}&p={page}"


class Job51Adapter(BaseSiteAdapter):
    site = "51job"
    spec = XPathSiteSpec(
        list_wait_xpath=(
            "//div[contains(@class,'joblist')]"
            " | //div[contains(@class,'joblist-item')]"
            " | //div[contains(@class,'job-item')]"
        ),
        card_xpath="//div[contains(@class,'joblist-item-job')]",
        title_xpath=(
            ".//span[contains(@class,'jname')]/text()"
            " | .//a[contains(@class,'job-title')]//text()"
            " | .//span[contains(@class,'job-name')]//text()"
        ),
        company_xpath=(
            ".//span[contains(@class,'cname')]/text()"
            " | .//a[contains(@class,'cname')]//text()"
            " | .//span[contains(@class,'company-name')]//text()"
        ),
        location_xpath=(
            ".//div[contains(@class,'area')]//text()"
            " | .//span[contains(@class,'job-area')]//text()"
            " | .//div[contains(@class,'job-area')]//text()"
        ),
        salary_xpath=(
            ".//span[contains(@class,'sal')]//text()"
            " | .//span[contains(@class,'salary')]//text()"
            " | .//div[contains(@class,'salary')]//text()"
        ),
        experience_xpath=(
            ".//span[contains(@class,'experience')]//text()"
            " | .//span[contains(@class,'exp')]//text()"
            " | .//div[contains(@class,'job-info')]//span[1]//text()"
        ),
        degree_xpath=(
            ".//span[contains(@class,'degree')]//text()"
            " | .//span[contains(@class,'education')]//text()"
            " | .//div[contains(@class,'job-info')]//span[2]//text()"
        ),
        tags_xpath=(
            ".//div[contains(@class,'tags')]//div[contains(@class,'tag')]/text()"
            " | .//span[contains(@class,'tag')]//text()"
            " | .//div[contains(@class,'job-tags')]//text()"
        ),
        summary_xpath=(
            ".//div[contains(@class,'job-desc')]//text()"
            " | .//p[contains(@class,'desc')]//text()"
        ),
        link_xpath=(
            ".//a[contains(@href,'jobs.51job.com')][1]/@href"
        ),
        detail_wait_xpath=(
            "//div[contains(concat(' ', normalize-space(@class), ' '), ' job_msg ')]"
            " | //div[contains(concat(' ', normalize-space(@class), ' '), ' job-inform ')]"
            " | //div[contains(@class,'jobdetail')]"
        ),
        detail_title_xpath=(
            "//h1[contains(@class,'job-title')]/text()"
            " | //div[contains(@class,'job-title')]//text()"
        ),
        detail_company_xpath=(
            "//a[contains(@class,'company-name')]/text()"
            " | //div[contains(@class,'company-name')]//text()"
        ),
        detail_location_xpath=(
            "//span[contains(@class,'job-area')]/text()"
            " | //div[contains(@class,'job-address')]//text()"
        ),
        detail_salary_xpath=(
            "//span[contains(@class,'salary')]/text()"
            " | //div[contains(@class,'job-salary')]//text()"
        ),
        detail_experience_xpath=(
            "//div[contains(@class,'job-require')]//span[1]//text()"
            " | //span[contains(@class,'experience')]//text()"
        ),
        detail_degree_xpath=(
            "//div[contains(@class,'job-require')]//span[2]//text()"
            " | //span[contains(@class,'degree')]//text()"
        ),
        detail_tags_xpath=(
            "//div[contains(@class,'tag-box')]//text()"
            " | //span[contains(@class,'job-tag')]/text()"
        ),
        detail_description_xpath=(
            "//div[contains(@class,'job-inform')]//text()"
            " | //div[contains(@class,'bmsg job_msg inbox')]//text()"
        ),
    )

    def build_search_url(self, keyword: str, city: str, page: int) -> str:
        return (
            "https://we.51job.com/pc/search?"
            f"keyword={quote_plus(keyword)}&searchType=2&sortType=0&pageNum={page}&jobArea={quote_plus(city)}"
        )

    def parse_list_page(self, page_source: str) -> list[JobRecord]:
        tree = html.fromstring(page_source)
        cards = tree.xpath(self.spec.card_xpath)
        rows: list[JobRecord] = []
        scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        seen_urls: set[str] = set()

        for card in cards:
            sensors_raw = _clean(card.attrib.get("sensorsdata", ""))
            sensors: dict[str, object] = {}
            if sensors_raw:
                try:
                    sensors = json.loads(html_lib.unescape(sensors_raw))
                except json.JSONDecodeError:
                    sensors = {}

            if not sensors:
                continue

            job_url = _normalize_url(_extract_first(card, self.spec.link_xpath), self.site)
            if not job_url:
                continue
            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)

            title = _extract_first(card, self.spec.title_xpath) or _clean(sensors.get("jobTitle"))
            company = _extract_first(card, self.spec.company_xpath)
            location = _clean(sensors.get("jobArea")) or _extract_first(card, self.spec.location_xpath)
            salary = _extract_first(card, self.spec.salary_xpath) or _clean(sensors.get("jobSalary"))
            experience = _clean(sensors.get("jobYear"))
            degree = _clean(sensors.get("jobDegree"))
            tags = _extract_joined(card, self.spec.tags_xpath)
            summary = _extract_joined(card, self.spec.summary_xpath)

            if not any([title, company, location, salary, job_url]):
                continue

            rows.append(
                JobRecord(
                    title=title,
                    company=company,
                    location=location,
                    salary=salary,
                    experience=experience,
                    degree=degree,
                    tags=tags,
                    job_description=summary,
                    job_url=job_url,
                    source=self.site,
                    scraped_at=scraped_at,
                )
            )

        return rows

    def wait_for_detail_page(self, driver: webdriver.Chrome, timeout: int) -> None:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, self.spec.detail_wait_xpath))
        )

    def parse_detail_page(self, page_source: str, base_row: JobRecord) -> JobRecord:
        tree = html.fromstring(page_source)

        description = _extract_joined(
            tree,
            (
                "//div[contains(concat(' ', normalize-space(@class), ' '), ' bmsg ')"
                " and contains(concat(' ', normalize-space(@class), ' '), ' job_msg ')]//text()"
                " | //div[contains(concat(' ', normalize-space(@class), ' '), ' job-inform ')]//text()"
                " | //div[contains(@class,'inbox')]//text()"
                " | //div[contains(@class,'jobdetail')]//text()"
                " | //div[contains(@class,'detail-content')]//text()"
                " | //section[contains(@class,'job-detail')]//text()"
                " | //div[contains(@class,'job-content')]//text()"
            ),
        )

        if not description:
            description = _extract_with_regex(
                page_source,
                [
                    r'"jobDescribe"\s*:\s*"([^"]+)"',
                    r'"jobDescription"\s*:\s*"([^"]+)"',
                    r'"detail"\s*:\s*"([^"]{40,})"',
                    r'"description"\s*:\s*"([^"]{40,})"',
                ],
            )

        return JobRecord(
            title=base_row.title,
            company=base_row.company,
            location=base_row.location,
            salary=base_row.salary,
            experience=base_row.experience,
            degree=base_row.degree,
            tags=base_row.tags,
            job_description=description or base_row.job_description,
            job_url=base_row.job_url,
            source=self.site,
            scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )


SITE_ADAPTERS: dict[str, type[BaseSiteAdapter]] = {
    ZhaopinAdapter.site: ZhaopinAdapter,
    Job51Adapter.site: Job51Adapter,
}


class SeleniumSiteScraper:
    def __init__(
        self,
        site: str,
        keyword: str,
        city: str,
        pages: int,
        headless: bool,
        min_delay: float,
        max_delay: float,
        concurrency: int,
        timeout: int,
    ):
        if site not in SITE_ADAPTERS:
            raise ValueError(f"Unsupported site: {site}")
        self.adapter = SITE_ADAPTERS[site]()
        self.keyword = keyword
        self.city = city
        self.pages = max(1, pages)
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max(max_delay, min_delay)
        self.concurrency = max(1, min(concurrency, self.pages))
        self.timeout = timeout
        self._print_lock = threading.Lock()

    def _sleep(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _log(self, message: str) -> None:
        with self._print_lock:
            print(message)

    def _scrape_page_batch(self, page_numbers: list[int], worker_id: int) -> list[JobRecord]:
        rows: list[JobRecord] = []
        driver = _create_driver(self.headless)
        try:
            for page_no in page_numbers:
                url = self.adapter.build_search_url(self.keyword, self.city, page_no)
                self._log(f"[INFO] worker={worker_id} page={page_no} url={url}")
                self._sleep()
                try:
                    driver.get(url)
                    self.adapter.wait_for_list_page(driver, self.timeout)
                    self._sleep()
                    rows.extend(self.adapter.parse_list_page(driver.page_source))
                except TimeoutException:
                    self._log(f"[WARN] worker={worker_id} page={page_no} timed out")
                except WebDriverException as exc:
                    self._log(f"[WARN] worker={worker_id} page={page_no} driver error: {exc}")
        finally:
            driver.quit()
        return rows

    def _enrich_detail_batch(self, batch: list[JobRecord], worker_id: int) -> list[JobRecord]:
        rows: list[JobRecord] = []
        driver = _create_driver(self.headless)
        try:
            for row in batch:
                if not row.job_url:
                    rows.append(row)
                    continue
                self._log(f"[INFO] detail-worker={worker_id} url={row.job_url}")
                self._sleep()
                try:
                    driver.get(row.job_url)
                    self.adapter.wait_for_detail_page(driver, self.timeout)
                    self._sleep()
                    rows.append(self.adapter.parse_detail_page(driver.page_source, row))
                except TimeoutException:
                    self._log(f"[WARN] detail-worker={worker_id} timeout url={row.job_url}")
                    rows.append(row)
                except WebDriverException as exc:
                    self._log(f"[WARN] detail-worker={worker_id} driver error: {exc}")
                    rows.append(row)
        finally:
            driver.quit()
        return rows

    def run(self) -> list[JobRecord]:
        page_chunks = _chunk_pages(self.pages, self.concurrency)
        all_rows: list[JobRecord] = []

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {
                executor.submit(self._scrape_page_batch, chunk, idx + 1): idx + 1
                for idx, chunk in enumerate(page_chunks)
            }
            for future in as_completed(futures):
                worker_id = futures[future]
                try:
                    worker_rows = future.result()
                    self._log(f"[INFO] worker={worker_id} collected={len(worker_rows)}")
                    all_rows.extend(worker_rows)
                except Exception as exc:
                    self._log(f"[WARN] worker={worker_id} failed: {exc}")

        deduped_rows = _dedupe_rows(all_rows)
        if not deduped_rows:
            return deduped_rows
        if not self.adapter.should_enrich_detail():
            return deduped_rows

        detail_chunks = _chunk_records(deduped_rows, self.concurrency)
        enriched_rows: list[JobRecord] = []

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {
                executor.submit(self._enrich_detail_batch, chunk, idx + 1): idx + 1
                for idx, chunk in enumerate(detail_chunks)
            }
            for future in as_completed(futures):
                worker_id = futures[future]
                try:
                    worker_rows = future.result()
                    self._log(f"[INFO] detail-worker={worker_id} collected={len(worker_rows)}")
                    enriched_rows.extend(worker_rows)
                except Exception as exc:
                    self._log(f"[WARN] detail-worker={worker_id} failed: {exc}")

        return _dedupe_rows(enriched_rows)


def save_to_csv(rows: list[JobRecord], output: str) -> None:
    os.makedirs(os.path.dirname(output), exist_ok=True)
    headers = list(
        JobRecord(
            title="",
            company="",
            location="",
            salary="",
            experience="",
            degree="",
            tags="",
            job_description="",
            job_url="",
            source="",
            scraped_at="",
        ).__dict__.keys()
    )

    with open(output, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    print(f"[INFO] saved {len(rows)} rows -> {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape job data from job sites with Selenium + site adapters")
    parser.add_argument("--site", choices=sorted(SITE_ADAPTERS.keys()), required=True)
    parser.add_argument("--keyword", type=str, default="大数据")
    parser.add_argument("--city", type=str, default="上海", help="城市名称或站点支持的地区编码")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=2, help="并发 driver 数，建议 1-2")
    parser.add_argument("--min-delay", type=float, default=0.5)
    parser.add_argument("--max-delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    scraper = SeleniumSiteScraper(
        site=args.site,
        keyword=args.keyword,
        city=args.city,
        pages=args.pages,
        headless=args.headless,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        concurrency=args.concurrency,
        timeout=args.timeout,
    )
    rows = scraper.run()
    save_to_csv(rows, args.output)


if __name__ == "__main__":
    main()
