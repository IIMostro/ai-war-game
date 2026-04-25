"""领域错误层级。"""


class AIWarGameError(Exception):
    """所有项目自定义错误的根。"""


class HermesUnavailableError(AIWarGameError):
    """Hermes 环境检查失败。"""


class ScenarioGenerationError(AIWarGameError):
    """Hermes 调用本身失败 (非空输出但报错或子进程异常)."""


class ScenarioInvalidError(AIWarGameError):
    """Hermes 返回结构不符合最小要求。"""


class SaveNotFoundError(AIWarGameError):
    """请求的存档不存在。"""


class SaveCorruptedError(AIWarGameError):
    """存档损坏或 schema 版本不识别。"""


class InvalidCommandError(AIWarGameError):
    """玩家命令无法被领域层处理。"""
