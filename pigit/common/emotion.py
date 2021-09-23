# -*- coding:utf-8 -*-
import sys

# For encoding.
Icon_Supported_Encoding: list = ["utf-8"]


class Emotion(object):
    # XXX(zachary): There are some problems with the output emotion on windows.
    # ? In CMD, encoding is right, but emotion is error.
    # ? In git bash, encoding is not right, but seem can't detection.
    if (
        not sys.platform.lower().startswith("win")
        and sys.getdefaultencoding().lower() in Icon_Supported_Encoding
    ):
        Icon_Rainbow = "🌈"
        Icon_Smiler = "😊"
        Icon_Thinking = "🧐"
        Icon_Sorry = "😅"
    else:
        Icon_Rainbow = "::"
        Icon_Smiler = "^_^"
        Icon_Thinking = "-?-"
        Icon_Sorry = "Orz"
