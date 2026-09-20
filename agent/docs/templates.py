"""Fixed Chinese string constants for user manual docx generation.

All dynamic substitutions use Python str.format() with named fields.
Module-related templates take {label} (module.label) and {entity}
(LLM-generated short singular name).
"""

# ===== 页眉 =====
HEADER_TEXT = "{name}{version}使用手册"

# ===== 系统概述（fallback）=====
SYSTEM_OVERVIEW_FALLBACK = "{name}包括{module_list}。"

# ===== 技术栈段落（固定）=====
TECH_STACK_PARAGRAPH = (
    "系统采用主流B/S系统架构，以Python语言进行开发。"
    "采用Flask-Admin开发框架，以SQLite3作为数据库，"
    "并使用SQLAlchemy ORM库进行数据访问，实现快速搭建项目。"
    "登录功能采用Flask-Login、Flask-WTF框架实现，简洁高效。"
)

# ===== 第2章 软件编译（固定）=====
SECTION_COMPILE_INTRO = "本软件使用Visual Studio Code进行开发，需要使用相同软件进行开发编译。"
SECTION_COMPILE_DEV_UI = "软件开发界面："
SECTION_COMPILE_BUILD_OK = "编译成功画面："

# ===== 第3章 软件安装（固定）=====
INSTALL_PYTHON = (
    "首先需要装好 Python 3环境，版本在 3.9以上即可，"
    "可以在 python 官网下载相关安装包按照说明安装即可。"
)

INSTALL_DEPS_STEPS = [
    "先创建虚拟环境：",
    "python -m venv venv",
    "激活虚拟环境：",
    "source venv/bin/activate",
    "在命令行输入以下命令安装相关依赖包：",
    "pip install -r requirements.txt",
    "如下图所示，表示已经安装成功了。",
]

INSTALL_START_INTRO = "通过以下命令来启动系统："
INSTALL_START_CMD = "python app.py"
INSTALL_START_OK = "输出以下内容表示系统已经启动成功。"

INSTALL_VERIFY_INTRO = (
    "在浏览器中输入地址：http://127.0.0.1:5000/admin/ "
    "即可进入系统登录页面："
)
INSTALL_VERIFY_OK = "登录成功后进入系统首页："

# ===== 第5章 技术规格（固定）=====
TECH_HARDWARE_REQS = [
    "CPU：双核 2.0 GHz 及以上",
    "内存：4 GB 及以上",
    "硬盘：20 GB 可用空间",
]

TECH_SOFTWARE_REQS = [
    "操作系统：Windows / Linux / macOS",
    "Python：3.9 及以上",
    "数据库：SQLite 3",
    "浏览器：Chrome / Firefox / Edge 最新版",
]

# ===== 第6章 附录（固定）=====
GLOSSARY = [
    ("SQLite3", "一种轻量级的关系型数据库管理系统。"),
    ("ORM", "对象关系映射，用于面向对象编程语言与关系数据库之间的数据转换。"),
    ("B/S", "Browser/Server 架构，客户端通过浏览器访问服务端应用。"),
    ("Flask-Admin", "基于 Flask 的后台管理框架，提供 CRUD 界面自动生成能力。"),
]

REFERENCES = [
    ("SQLAlchemy", "https://docs.sqlalchemy.org/en/14/"),
    ("SQLite3", "https://www.sqlite.org/docs.html"),
    ("Flask", "https://flask.palletsprojects.com/en/2.0.x/"),
    ("Flask-Admin", "https://flask-admin.readthedocs.io/en/latest/"),
    ("Flask-Login", "https://flask-login.readthedocs.io/en/latest/"),
    ("Flask-WTF", "https://flask-wtf.readthedocs.io/en/1.2.x/"),
]

# ===== 1.1 核心功能 - 每模块4条能力 =====
CORE_FEATURE_TEMPLATES = [
    "新增{entity}信息：用户可以在该模块中新增{entity}信息。",
    "编辑{entity}信息：用户可以在该模块中编辑已有的{entity}信息。",
    "删除{entity}信息：用户可以在该模块中删除已有的{entity}信息。",
    "查询{entity}信息：用户可以在该模块中查询已有的{entity}信息。",
]

# ===== 第4章 模块动态段落（按 {label} 和 {entity} 填充）=====
MODULE_INTRO = "点击【{label}】，即可展示{entity}信息列表，如下图所示："

CREATE_STEP1 = "在【{label}】页面，点击【创建】按钮，即可新增{entity}信息记录，如下图所示："
CREATE_STEP2 = "填写相关基础信息字段后点击【保存】："
CREATE_STEP3 = "创建成功后即可在列表页面中看到新增的{entity}信息："

QUERY_STEP1 = "在{label}列表页面上方选择【新增筛选器】，选择筛选条件："
QUERY_STEP2 = "如输入关键词，点击【应用】，即可搜到包含该信息的相关记录："

DELETE_STEP1 = "在【{label}】列表页面，点击记录前的删除按钮，即可删除对应的信息。"
DELETE_STEP2 = "在删除前，会弹出确认对话框："
DELETE_STEP3 = "点击【确定】后，该{entity}信息即可删除。"

# ===== 文件修订记录初始行 =====
REVISION_INITIAL_CONTENT = "初始版本"
