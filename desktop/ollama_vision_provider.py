import json
import os

import ollama

from desktop.vision_provider import VisionProvider


class OllamaVisionProvider(VisionProvider):
    """
    Local visual-understanding provider using Ollama.

    Responsibilities:
        - send screenshots to a multimodal model
        - request semantic UI targets
        - preserve raw model output for diagnostics
        - parse structured JSON output

    This provider has NO mouse or keyboard authority.
    """

    provider_name = "ollama_qwen3_vl"
    provider_type = "local_multimodal"

    def __init__(
        self,
        model="qwen3-vl:2b",
    ):
        self.model = model

    def is_available(self):
        """
        Check whether the configured model exists
        in the local Ollama installation.
        """

        try:
            response = ollama.list()

            models = getattr(
                response,
                "models",
                None,
            )

            if (
                models is None
                and isinstance(response, dict)
            ):
                models = response.get(
                    "models",
                    [],
                )

            models = models or []

            for model in models:

                name = getattr(
                    model,
                    "model",
                    None,
                )

                if (
                    name is None
                    and isinstance(model, dict)
                ):
                    name = (
                        model.get("model")
                        or model.get("name")
                    )

                if name == self.model:
                    return True

            return False

        except Exception:
            return False

    def _build_prompt(
        self,
        query,
    ):
        """
        Build the visual-grounding prompt.
        """

        return f"""
You are a desktop UI visual-grounding system.

Analyze the supplied screenshot of an application window.

Find UI elements matching this request:

{query}

Return ONLY one JSON object.

Required format:

{{
  "targets": [
    {{
      "label": "short semantic label",
      "target_type": "button",
      "confidence": 0.95,
      "x": 100,
      "y": 200,
      "width": 150,
      "height": 40,
      "text": "visible text if any",
      "description": "brief description"
    }}
  ]
}}

Allowed target_type values:

button
text_field
search_field
menu
menu_item
tab
list
list_item
checkbox
radio_button
link
text
icon
image
unknown

IMPORTANT COORDINATE RULES:

- x and y are the TOP-LEFT corner of the target.
- width and height describe the target bounding box.
- Coordinates MUST be relative to the supplied screenshot.
- Do NOT use absolute desktop coordinates.
- Do NOT invent a target that is not visible.
- confidence must be between 0.0 and 1.0.

If no matching target is visible, return:

{{"targets": []}}

Do not include markdown.
Do not include explanations outside the JSON.
""".strip()

    def find_targets(
        self,
        image_path,
        query,
    ):
        """
        Analyze an application screenshot and return
        raw semantic UI targets.
        """

        result = {
            "success": False,
            "provider": self.provider_name,
            "model": self.model,
            "query": query,
            "targets": [],
            "raw_response": None,
            "error": None,
        }

        if (
            not isinstance(image_path, str)
            or not os.path.isfile(image_path)
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

        if not self.is_available():
            result["error"] = (
                f"Ollama model "
                f"{self.model!r} "
                f"is not available."
            )
            return result

        prompt = self._build_prompt(
            query
        )

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [
                            image_path
                        ],
                    }
                ],
                format="json",
                options={
                    "temperature": 0,
                },
            )

        except Exception as error:
            result["error"] = (
                f"Ollama vision request "
                f"failed: {error}"
            )
            return result

        try:
            content = response[
                "message"
            ][
                "content"
            ]

        except Exception:
            result["error"] = (
                "Ollama returned an "
                "unexpected response."
            )
            return result

        # Preserve the exact model output.
        # This is useful for debugging provider
        # formatting problems.
        result["raw_response"] = content

        try:
            parsed = json.loads(
                content
            )

        except Exception as error:
            result["error"] = (
                f"Vision model returned "
                f"invalid JSON: {error}"
            )
            return result

        if not isinstance(
            parsed,
            dict,
        ):
            result["error"] = (
                "Vision model response "
                "must be a JSON object."
            )
            return result

        targets = parsed.get(
            "targets",
            [],
        )

        if not isinstance(
            targets,
            list,
        ):
            result["error"] = (
                "Vision model returned "
                "an invalid targets field."
            )
            return result

        normalized_targets = []

        for target in targets:

            if not isinstance(
                target,
                dict,
            ):
                continue

            normalized_target = dict(
                target
            )

            normalized_target[
                "source"
            ] = self.provider_name

            normalized_targets.append(
                normalized_target
            )

        result["targets"] = (
            normalized_targets
        )

        result["success"] = True

        return result


if __name__ == "__main__":

    provider = (
        OllamaVisionProvider()
    )

    print(
        "Provider:",
        provider.get_info(),
    )