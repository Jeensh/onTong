package com.example.slabdesign.boot.config;

import org.springframework.context.annotation.Configuration;

@Configuration
public class DataSourceConfig {
    // P1 placeholder. Actual DataSource bean wiring comes in P3 (Edges).
    // Spring Boot autoconfig (HikariCP + Oracle) handles it via application.yml at runtime.
}
