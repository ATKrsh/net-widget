FROM python:3.11-slim-bookworm

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for GUI (X11, OpenGL, DBus, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglx0 \
    libglib2.0-0 \
    libdbus-1-3 \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-sync1 \
    libxcb-util1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libfontconfig1 \
    libxrender1 \
    libxi6 \
    libxrandr2 \
    libxcursor1 \
    libxcomposite1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*


# Set working directory
WORKDIR /app

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code files
COPY . .

# Set dynamic library variables for Qt/OpenGL
ENV LIBGL_ALWAYS_INDIRECT=1

# Run the app
CMD ["python", "main.py"]
