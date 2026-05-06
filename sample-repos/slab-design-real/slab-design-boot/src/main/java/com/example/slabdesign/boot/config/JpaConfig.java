package com.example.slabdesign.boot.config;

import org.springframework.context.annotation.Configuration;

@Configuration
public class JpaConfig {
    // P1 placeholder. JPA scanning is done at @SpringBootApplication via @EntityScan + @EnableJpaRepositories.
    // P3 may add EntityManagerFactory / TransactionManager customization here.
}
