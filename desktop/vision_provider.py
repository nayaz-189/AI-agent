from abc import ABC, abstractmethod


class VisionProvider(ABC):
    """
    Base contract for every visual-understanding
    provider used by the desktop system.

    A provider may eventually be:
        - a local vision model
        - a cloud multimodal model
        - OCR
        - another AI agent
        - another perception system

    Providers analyze images only.
    They do not click, type, or control applications.
    """

    provider_name = "base"
    provider_type = "unknown"

    def get_info(self):
        """
        Return basic provider metadata.
        """

        return {
            "name": self.provider_name,
            "type": self.provider_type,
            "available": self.is_available(),
        }

    @abstractmethod
    def is_available(self):
        """
        Return True when this provider is ready
        to perform visual analysis.
        """

        raise NotImplementedError

    @abstractmethod
    def find_targets(
        self,
        image_path,
        query,
    ):
        """
        Find UI elements matching a semantic query.

        Example:

            query = "search field"

        Expected result:

            {
                "success": True,
                "provider": "...",
                "query": "search field",
                "targets": [...],
                "error": None
            }

        Each target will eventually be normalized
        into the project's UITarget contract.
        """

        raise NotImplementedError