-- Create test_user role if not exists (POSTGRES_USER already creates it,
-- but this ensures the role exists for any init-time grants).
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'test_user') THEN
      CREATE ROLE test_user LOGIN PASSWORD 'test_password';
   END IF;
END
$do$;

-- Grant privileges on test_smarttoll database
GRANT ALL PRIVILEGES ON DATABASE test_smarttoll TO test_user;
