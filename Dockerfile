FROM anaconda/miniconda:latest

WORKDIR /app
COPY environment.yml .

# Accept ToS via environment variable, create environment, and set it as default
ENV CONDA_PLUGINS_AUTO_ACCEPT_TOS=true
RUN conda env create -f environment.yml && \
    conda config --set default_activation_env rewild_dashboard

SHELL ["conda", "run", "/bin/bash", "-c"]

COPY src ./src
COPY gunicorn.conf.py .

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "rewild_dashboard", "gunicorn", "--worker-tmp-dir", "/dev/shm","app:server", "--bind", "0.0.0.0:8000"]
