import logging

from threading import Lock

from chrome_extension_python import Extension

logging.basicConfig(level=logging.DEBUG)

lock = Lock()


def perform_sadcaptcha_file_updates(ext: Extension, api_key):
    ext.get_file("script.js").update_contents(lambda x: update_js_contents(x, api_key))


def update_js_contents(content: str, api_key: str):
    return content.replace(
        'var apiKey = localStorage.getItem("sadCaptchaKey");',
        f'var apiKey = "{api_key}";',
    )


class SadCaptcha(Extension):
    def __init__(self, api_key):
        super().__init__(
            extension_id="beojaiildognffpjmpiamfofnplkdfih",
            extension_name="Sad Captcha",
            api_key=api_key,
        )

    def update_files(self, api_key):
        js_files = self.get_js_files()
        logging.debug("Updating files")
        for file in js_files:
            file.update_contents(lambda x: update_js_contents(x, api_key))
