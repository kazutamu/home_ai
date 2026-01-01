FROM mcr.microsoft.com/devcontainers/python:3.11

# Install system deps for audio and playback; clean to keep image small.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libsndfile1 cargo portaudio19-dev libportaudio2 libportaudiocpp0 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv (https://docs.astral.sh/uv/) as the vscode user so it lands in the right home.
USER vscode
ENV PATH="/home/vscode/.local/bin:${PATH}"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
