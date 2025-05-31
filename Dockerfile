FROM python:3.12-slim-bookworm


# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"


ADD . /app
WORKDIR /app

RUN uv sync --locked

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

CMD ["uv", "run", "streamlit", "run", "src/viewer/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
