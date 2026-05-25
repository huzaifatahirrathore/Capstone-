-- SQL for plantation projects table
CREATE TABLE plantation_projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    location VARCHAR(255),
    start_date DATE,
    end_date DATE,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);
