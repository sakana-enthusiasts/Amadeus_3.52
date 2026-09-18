"""毒性证据展示设置。当前实验途径必须由用户显式配置。"""

当前动物实验给药途径: str | None = None
当前动物实验物种: str | None = None
当前动物实验暴露时长: str | None = None
当前动物实验暴露模式: str | None = None  # 单次／重复，未配置时不推断
当前主要关注终点: str | None = None
CompTox密钥环境变量 = "COMPTOX_API_KEY"
严重危险自动规则: list[dict[str, str]] = []  # 本轮为空：不以毒性自动淘汰候选
