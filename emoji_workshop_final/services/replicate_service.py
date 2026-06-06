from services.animation_service import AIAnimationService, AnimationGenerateWorker


class ReplicateService(AIAnimationService):
    """向后兼容旧导入路径。"""


StickerGenerateWorker = AnimationGenerateWorker
