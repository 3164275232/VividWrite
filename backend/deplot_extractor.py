"""DePlot 图表数据抽取封装。

避免在模块导入阶段立即加载大型权重，防止：
1. 无网络 / 缺依赖时报错导致函数名未定义，引发 ImportError。
2. 进程多实例（Uvicorn reload/multiprocessing）重复下载或占用显存/内存。

改为懒加载：首次调用时再加载模型，并进行简单缓存。
"""
from typing import Optional, Any
from PIL import Image

try:
    from transformers import Pix2StructProcessor, Pix2StructForConditionalGeneration  # type: ignore
except ImportError as e:  # transformers 未安装时仍允许模块导入，通过函数调用时报更清晰错误
    Pix2StructProcessor = Pix2StructForConditionalGeneration = None  # type: ignore

_deplot_processor: Optional[Any] = None
_deplot_model: Optional[Any] = None

_MODEL_NAME = "google/deplot"

def _ensure_model_loaded():
    global _deplot_processor, _deplot_model
    if _deplot_processor is not None and _deplot_model is not None:
        return
    if Pix2StructProcessor is None or Pix2StructForConditionalGeneration is None:
        raise RuntimeError("transformers 未安装，无法使用 DePlot。请先执行: pip install transformers pillow")
    try:
        _deplot_processor = Pix2StructProcessor.from_pretrained(_MODEL_NAME)
        _deplot_model = Pix2StructForConditionalGeneration.from_pretrained(_MODEL_NAME)
    except Exception as e:  # 捕获下载/加载失败
        raise RuntimeError(f"加载 DePlot 模型失败: {e}") from e


def extract_table_from_image_deplot(image_path: str) -> str:
    """从图像中抽取底层表格文本。

    返回的原始字符串中保留模型生成内容，不做 <0x0A> 转换，调用方决定格式化。
    """
    _ensure_model_loaded()
    assert _deplot_processor is not None and _deplot_model is not None
    image = Image.open(image_path).convert("RGB")
    inputs = _deplot_processor(images=image, text="Generate underlying data table of the figure below:", return_tensors="pt")
    predictions = _deplot_model.generate(**inputs, max_new_tokens=512)
    return _deplot_processor.decode(predictions[0], skip_special_tokens=True)