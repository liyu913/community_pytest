# 社区接口自动化测试

基于 pytest、requests 和 Allure，测试环境为 https://developer-dev.d-robotics.cc。
接口文档：https://developer-dev.d-robotics.cc/swagger-ui/index.html#/

## 项目结构

- api/login_api.py：登录和查询当前用户。
- api/case_api.py：创建、发布、查询和删除案例。
- api/skill_api.py：提交技能、查询审核与公开文件、删除技能。
- api/asset_api.py：申请上传凭证、上传图片和技能 ZIP。
- common/request_client.py：公共请求、Bearer 认证、日志与报告附件。
- config/config.yaml：测试环境和公共登录账号。
- data/login.yaml：登录成功和失败场景。
- data/case.yaml、data/skill.yaml：发布流程的数据、素材路径和执行开关。
- tests/：登录、用户查询、案例发布和技能发布用例。
- utils/：YAML 读取、日志和通用断言工具。
- conftest.py：准备带 Token 和不带 Token 的请求对象。

## 安装与运行

在项目根目录执行：

```powershell
python -m pip install -r requirements.txt
python -m pytest
```

只检查用例能否收集，不向服务器发送请求：

```powershell
python -m pytest --collect-only
```

单独运行一个模块：

```powershell
python -m pytest tests/test_login.py -v
python -m pytest tests/test_current_user.py -v
python -m pytest tests/test_case.py -v
python -m pytest tests/test_skill.py -v
```

本机可用解释器为 D:\yuuuu\python\python.exe，也可以使用它的完整路径运行上述命令。

## 发布流程配置

案例和技能用例分别读取 data/case.yaml、data/skill.yaml。
当 enabled 为 false 时跳过该流程；填好素材并改为 true 后才实际执行。
开启后会上传文件并创建测试内容，流程结束时删除本次创建的案例或技能。

案例流程：上传封面 → 创建草稿 → 发布 → 作者和公开详情校验 → 清理。
技能流程：上传图标及 ZIP → 提交 → 等待审核 → 公开详情及文件校验 → 清理。
技能审核等待时长和查询间隔在 data/skill.yaml 中配置。

## 日志和报告

日志位于 logs/。当前请求封装会记录完整请求和响应，日志可能包含账号密码和 Token，请勿直接分享。

```powershell
python run.py
allure serve reports/allure-results
```

run.py 会运行 pytest 并生成 Allure 结果；查看报告需要安装 Allure CLI。
