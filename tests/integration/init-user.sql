-- Create smarttoll_user role and database if not exists
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'smarttoll_user') THEN
      CREATE ROLE smarttoll_user LOGIN PASSWORD 'changeme_in_prod_123!';
   END IF;
END
$do$;

-- Grant privileges on smarttoll_dev database
GRANT ALL PRIVILEGES ON DATABASE smarttoll_dev TO smarttoll_user;
