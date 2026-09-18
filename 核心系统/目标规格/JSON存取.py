"""纯 JSON 存取；无默认保存目录，不读取数据库或自动挂接旧流程。"""

import json
import os
from pathlib import Path
import tempfile

from .数据结构 import ProfileValidationError, TargetProfile


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileValidationError(f"JSON 键重复：{key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ProfileValidationError(f"JSON 不接受非有限数值：{value}")


def import_profile_json(content: str) -> TargetProfile:
    if not isinstance(content, str):
        raise ProfileValidationError("JSON 输入必须为字符串")
    try:
        data = json.loads(content.removeprefix("\ufeff"), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except json.JSONDecodeError as error:
        raise ProfileValidationError(f"JSON 格式错误：{error}") from error
    return TargetProfile.from_dict(data)


def export_profile_json(profile: TargetProfile) -> str:
    if not isinstance(profile, TargetProfile):
        raise ProfileValidationError("必须提供 TargetProfile")
    # 导出边界再次验证；没有候选值、计算结果、模型参数等扩展槽。
    data = TargetProfile.from_dict(profile.to_dict()).to_dict()
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def save_profile(profile: TargetProfile, path, *, overwrite: bool = False) -> Path:
    """显式路径；父目录必须存在。默认不覆盖，覆盖时原子替换文件。"""
    content = export_profile_json(profile)
    target = Path(path)
    if target.suffix.lower() != ".json":
        raise ProfileValidationError("保存文件须使用 .json 后缀")
    if not isinstance(overwrite, bool):
        raise ProfileValidationError("overwrite 必须为布尔值")
    if not overwrite:
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        return target
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=target.parent, prefix=".target-profile-",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def load_profile(path) -> TargetProfile:
    return import_profile_json(Path(path).read_text(encoding="utf-8-sig"))
