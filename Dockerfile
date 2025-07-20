FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    git \
    libstdc++6 \
    libgcc-s1 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

ENV HUGO_VERSION 0.148.1

RUN curl -L https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_Linux-64bit.tar.gz \
    -o hugo.tar.gz \
 && tar -xzf hugo.tar.gz \
 && mv hugo /usr/local/bin/hugo \
 && chmod +x /usr/local/bin/hugo \
 && rm hugo.tar.gz

WORKDIR /site
VOLUME ["/site"]
CMD ["hugo"]

#CMD ["server", "--bind", "0.0.0.0", "--buildDrafts", "--watch"]

