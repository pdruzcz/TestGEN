package com.example.processor;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Przetwarzacz danych — probka z parametryzacja.
 */
public class DataProcessor {

    public int sum(List<Integer> numbers) {
        if (numbers == null) {
            throw new IllegalArgumentException("Numbers list cannot be null");
        }
        return numbers.stream().mapToInt(Integer::intValue).sum();
    }

    public List<String> filterAndTransform(List<String> input, int minLength) {
        if (input == null) {
            return List.of();
        }
        return input.stream()
            .filter(s -> s != null && s.length() >= minLength)
            .map(String::toUpperCase)
            .collect(Collectors.toList());
    }

    public boolean isValid(String data) {
        return data != null && !data.isBlank() && data.length() <= 255;
    }
}
