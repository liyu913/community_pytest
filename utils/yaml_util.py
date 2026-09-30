from pathlib import Path

import yaml


# 当前文件路径是 utils/yaml_util.py
# parent 是 utils 目录，parent.parent 就是项目根目录
# 这样无论从哪里运行代码，都能找到正确的配置文件和测试数据文件
BASE_DIR = Path(__file__).resolve().parent.parent

# 环境配置文件路径：config/config.yaml
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"

# 登录接口测试数据文件路径：data/login.yaml
LOGIN_PATH = BASE_DIR / "data" / "login.yaml"

def read_yaml(file_path):
    """
    通用 YAML 读取方法。

    YAML 里的对象会转换成 Python dict，
    YAML 里的数组会转换成 Python list。
    """
    with open(file_path, mode="r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_config():
    """
    读取当前环境配置。

    config.yaml 里通过 env 字段控制当前环境，
    当前使用 env: dev，返回 dev 节点下的 base_url、username、password。
    """
    config = read_yaml(CONFIG_PATH)
    env = config["env"]
    return config[env]


def read_login_yaml():
    """
    读取登录接口测试数据。

    返回 data/login.yaml 里的 test_cases 列表，
    用于 pytest.mark.parametrize 参数化测试。
    """
    login_data = read_yaml(LOGIN_PATH)
    return login_data["test_cases"]


