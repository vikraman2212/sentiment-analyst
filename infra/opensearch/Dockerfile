FROM opensearchproject/opensearch:latest

ENV discovery.type=single-node
ENV DISABLE_INSTALL_DEMO_CONFIG=true
ENV DISABLE_SECURITY_PLUGIN=true
ENV OPENSEARCH_JAVA_OPTS="-Xms2g -Xmx2g"

EXPOSE 9200 9300

HEALTHCHECK --interval=30s --timeout=30s --retries=3 \
    CMD curl -fsS http://localhost:9200/_cluster/health || exit 1

CMD ["opensearch"]
