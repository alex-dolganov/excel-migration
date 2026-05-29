-- ==========================================================
--  MySQL setup for the Python (Django) backend.
--  Run this ONCE on the external MySQL server before first deploy.
--
--  After running this script, Django will manage all schema changes
--  automatically via: python manage.py migrate
--
--  Replace placeholders before executing:
--    <db-name>     → DB_NAME from .env
--    <db-user>     → DB_USER from .env
--    <db-password> → DB_PASSWORD from .env
-- ==========================================================

CREATE DATABASE IF NOT EXISTS `<db-name>`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS '<db-user>'@'%' IDENTIFIED BY '<db-password>';

GRANT ALL PRIVILEGES ON `<db-name>`.* TO '<db-user>'@'%';

FLUSH PRIVILEGES;
