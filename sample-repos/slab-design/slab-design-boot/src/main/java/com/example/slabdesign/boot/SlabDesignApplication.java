package com.example.slabdesign.boot;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

@SpringBootApplication
@ComponentScan(basePackages = "com.example.slabdesign")
@EntityScan(basePackages = "com.example.slabdesign.store")
@EnableJpaRepositories(basePackages = "com.example.slabdesign.store")
@MapperScan(basePackages = "com.example.slabdesign.store.mybatis", annotationClass = org.apache.ibatis.annotations.Mapper.class)
public class SlabDesignApplication {
    public static void main(String[] args) {
        SpringApplication.run(SlabDesignApplication.class, args);
    }
}
