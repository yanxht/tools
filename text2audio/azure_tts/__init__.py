# text2audio — Azure Neural TTS backend
#
# Self-contained text → audio renderer using Azure Neural TTS.
# No dependency on any other backend or shared package.
#
# NOTE: the package is named `azure_tts` (not `azure`) to avoid shadowing the
# `azure` namespace package that azure-cognitiveservices-speech installs.
#
# Usage:
#   python -m azure_tts.render -i story.md -o out.mp3
#   python -m azure_tts.render -i story.md -o out.mp3 --voice en-US-AvaMultilingualNeural
#   python -m azure_tts.render --list-voices
