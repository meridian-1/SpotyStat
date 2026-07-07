# from .base import *

# # DEBUG = False

# # Security (HTTPS)
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# TODO: подключить Redis для CACHES, когда появится больше одного
# воркера/процесса — иначе кэш из analytics/views.py работает лишь
# частично (см. обсуждение LocMemCache vs Redis)
