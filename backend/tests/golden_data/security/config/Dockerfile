FROM ubuntu:latest

RUN apt-get update && apt-get install -y sudo
ENV DB_PASSWORD=supersecret123

EXPOSE 5432

CMD ["./run.sh"]
