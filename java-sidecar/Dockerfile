FROM gradle:9.3.1-jdk25 AS build
WORKDIR /app
COPY build.gradle settings.gradle ./
COPY src ./src
RUN gradle installDist --no-daemon
FROM eclipse-temurin:25-jre
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/build/install/soop-unified-sidecar ./
EXPOSE 8091
CMD ["bin/soop-unified-sidecar"]
