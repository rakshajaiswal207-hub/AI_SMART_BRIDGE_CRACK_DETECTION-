-- Table 9.2. One row is one captured bridge-surface image.
CREATE DATABASE IF NOT EXISTS bridge_crack
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE bridge_crack;

CREATE TABLE IF NOT EXISTS inspections (
    id INT PRIMARY KEY AUTO_INCREMENT,
    captured_date DATE NOT NULL,
    captured_time TIME NOT NULL,
    original_path VARCHAR(255) NOT NULL,
    result_path VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    region_count INT NOT NULL
);