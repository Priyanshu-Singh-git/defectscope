# Self-host the Streamlit demo: docker build -f deploy/Dockerfile -t defectscope . && docker run -p 7860:7860 defectscope
FROM python:3.11-slim
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
# bake the pretrained backbone into the image so the app starts fast
RUN python -c "import timm; timm.create_model('resnet18.tv_in1k', pretrained=True, features_only=True)"
COPY --chown=user . .
EXPOSE 7860
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=7860", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
