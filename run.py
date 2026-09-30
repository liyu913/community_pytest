import sys
from pathlib import Path

import pytest


# 当前文件是 run.py
# Path(__file__) 表示当前文件路径
# resolve() 转成绝对路径
# parent 取 run.py 所在目录，也就是当前项目的根目录，不需要写死盘符。
BASE_DIR = Path(__file__).resolve().parent

# Allure 原始结果目录
# pytest 运行时会把 Allure 需要的数据写到这个目录
# 后面可以用 allure serve reports/allure-results 打开报告
ALLURE_RESULTS_DIR = BASE_DIR / "reports" / "allure-results"


def run_tests():
    """
    统一运行 pytest。

    直接在终端运行 pytest 也可以，
    但写到 run.py 里后，项目就有了统一的测试入口。

    pytest.ini 里已经配置了：
    - 测试目录 tests
    - 测试文件命名规则
    - 日志开关
    - 默认参数 -v

    这里额外指定 --alluredir，
    用来告诉 pytest 把 Allure 原始结果写到哪个目录。
    """
    # 取出命令后面指定的测试文件、-k 等参数，交给 pytest。
    user_args = sys.argv[1:]

    return pytest.main([
        # 指定 Allure 原始结果输出目录
        "--alluredir", str(ALLURE_RESULTS_DIR),

        # 由 Allure 插件清理旧结果，不再手动删除一次目录。
        # 这样本次报告不会混入上一次的测试结果。
        "--clean-alluredir"
    ] + user_args)


if __name__ == "__main__":
    # 只有直接运行 python run.py 时，下面代码才会执行

    # 运行 pytest，报告清理由上面的 --clean-alluredir 负责。
    # pytest.main() 会返回退出码：
    # 0 表示测试通过
    # 非 0 表示测试失败或执行异常
    #
    # raise SystemExit(...) 的作用是把 pytest 的退出码交给操作系统，
    # 这样命令行、CI/CD 工具就能知道本次测试是否成功。
    raise SystemExit(run_tests())
