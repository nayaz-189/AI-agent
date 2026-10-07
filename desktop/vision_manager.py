import os

from desktop.ui_target import (
    UITarget,
    validate_target,
)


class VisionManager:
    """
    Coordinates visual-understanding providers.

    Responsibilities:
        - register providers
        - inspect provider availability
        - select an available provider
        - request semantic targets
        - normalize provider results
        - validate UITarget objects

    This manager has no mouse or keyboard authority.
    """

    def __init__(self):
        self._providers = {}

    def register_provider(
        self,
        provider,
    ):
        """
        Register a visual-understanding provider.
        """

        if provider is None:
            raise ValueError(
                "Provider cannot be None."
            )

        name = getattr(
            provider,
            "provider_name",
            None,
        )

        if (
            not isinstance(name, str)
            or not name.strip()
        ):
            raise ValueError(
                "Provider must have a valid "
                "provider_name."
            )

        self._providers[name] = provider

    def unregister_provider(
        self,
        provider_name,
    ):
        """
        Remove a provider from this manager.
        """

        return self._providers.pop(
            provider_name,
            None,
        )

    def get_provider(
        self,
        provider_name,
    ):
        return self._providers.get(
            provider_name
        )

    def list_providers(self):
        """
        Return provider status without executing
        visual analysis.
        """

        providers = []

        for name, provider in (
            self._providers.items()
        ):
            try:
                available = bool(
                    provider.is_available()
                )
            except Exception:
                available = False

            providers.append(
                {
                    "name": name,
                    "type": getattr(
                        provider,
                        "provider_type",
                        "unknown",
                    ),
                    "available": available,
                }
            )

        return providers

    def select_provider(
        self,
        preferred=None,
    ):
        """
        Select an available provider.

        If preferred is supplied, only that provider
        is considered.

        Automatic policy is intentionally simple for
        now. More advanced routing comes later.
        """

        if preferred is not None:

            provider = self.get_provider(
                preferred
            )

            if provider is None:
                return None

            try:
                if provider.is_available():
                    return provider
            except Exception:
                return None

            return None

        for provider in (
            self._providers.values()
        ):
            try:
                if provider.is_available():
                    return provider
            except Exception:
                continue

        return None

    def _normalize_target(
        self,
        raw_target,
        provider_name,
    ):
        """
        Convert provider output into UITarget.
        """

        if isinstance(
            raw_target,
            UITarget,
        ):
            target = raw_target

        elif isinstance(
            raw_target,
            dict,
        ):
            try:
                target = UITarget(
                    label=raw_target.get(
                        "label",
                        "",
                    ),
                    target_type=raw_target.get(
                        "target_type",
                        "unknown",
                    ),
                    confidence=raw_target.get(
                        "confidence",
                        0.0,
                    ),
                    x=raw_target.get(
                        "x",
                        0,
                    ),
                    y=raw_target.get(
                        "y",
                        0,
                    ),
                    width=raw_target.get(
                        "width",
                        0,
                    ),
                    height=raw_target.get(
                        "height",
                        0,
                    ),
                    source=raw_target.get(
                        "source",
                        provider_name,
                    ),
                    text=raw_target.get(
                        "text"
                    ),
                    description=raw_target.get(
                        "description"
                    ),
                )

            except Exception:
                return None

        else:
            return None

        validation = validate_target(
            target
        )

        if not validation["valid"]:
            return None

        return target

    def find_targets(
        self,
        image_path,
        query,
        preferred_provider=None,
    ):
        """
        Find semantic UI targets in an image.

        Provider-specific output is converted into
        the project's standard UITarget format.
        """

        result = {
            "success": False,
            "query": query,
            "provider": None,
            "targets": [],
            "rejected_targets": 0,
            "error": None,
        }

        if (
            not isinstance(image_path, str)
            or not os.path.isfile(
                image_path
            )
        ):
            result["error"] = (
                "Image file does not exist."
            )
            return result

        if (
            not isinstance(query, str)
            or not query.strip()
        ):
            result["error"] = (
                "Visual query is required."
            )
            return result

        provider = self.select_provider(
            preferred_provider
        )

        if provider is None:
            result["error"] = (
                "No visual-understanding "
                "provider is available."
            )
            return result

        provider_name = getattr(
            provider,
            "provider_name",
            "unknown",
        )

        result["provider"] = (
            provider_name
        )

        try:
            provider_result = (
                provider.find_targets(
                    image_path,
                    query,
                )
            )

        except Exception as error:
            result["error"] = (
                f"Vision provider failed: "
                f"{error}"
            )
            return result

        if not isinstance(
            provider_result,
            dict,
        ):
            result["error"] = (
                "Vision provider returned "
                "an invalid result."
            )
            return result

        if not provider_result.get(
            "success"
        ):
            result["error"] = (
                provider_result.get(
                    "error"
                )
                or
                "Vision provider could not "
                "complete the request."
            )
            return result

        raw_targets = (
            provider_result.get(
                "targets",
                [],
            )
        )

        if not isinstance(
            raw_targets,
            list,
        ):
            result["error"] = (
                "Vision provider returned "
                "an invalid target list."
            )
            return result

        normalized = []

        rejected = 0

        for raw_target in raw_targets:

            target = (
                self._normalize_target(
                    raw_target,
                    provider_name,
                )
            )

            if target is None:
                rejected += 1
                continue

            normalized.append(
                target
            )

        # Highest-confidence target first.
        normalized.sort(
            key=lambda item: (
                item.confidence
            ),
            reverse=True,
        )

        result["targets"] = normalized

        result[
            "rejected_targets"
        ] = rejected

        result["success"] = True

        return result


if __name__ == "__main__":
    manager = VisionManager()

    print(
        "Registered providers:",
        manager.list_providers(),
    )

    print(
        "Selected provider:",
        manager.select_provider(),
    )