from typing import List, Optional
from pydantic import BaseModel, Field

class Skill(BaseModel):
    name: str = Field(description="技能名称，如 Python, Hadoop")
    category: Optional[str] = Field(description="技能类别，如 编程语言, 大数据组件")

class Major(BaseModel):
    name: str = Field(description="专业名称，如 计算机科学与技术")

class Degree(BaseModel):
    name: str = Field(description="学历要求，如 本科, 硕士")

class Location(BaseModel):
    city: str = Field(description="城市名称")

class JobExtractionResult(BaseModel):
    position_name: str = Field(description="岗位名称")
    skills: List[Skill] = Field(description="岗位要求的技能列表")
    majors: List[Major] = Field(description="优先考虑的专业列表")
    degree: Optional[Degree] = Field(description="最低学历要求")
    location: Optional[Location] = Field(description="工作地点")
    min_salary: Optional[float] = Field(description="最低薪资(k)")
    max_salary: Optional[float] = Field(description="最高薪资(k)")
