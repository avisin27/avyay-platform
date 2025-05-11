FROM nginx:alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY . /usr/share/nginx/html
RUN chmod -R 755 /usr/share/nginx/html

# Add a healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget --spider -q http://localhost || exit 1
  
EXPOSE 80
