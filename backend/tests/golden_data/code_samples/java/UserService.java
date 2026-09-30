package com.example.service;

import com.example.model.User;
import com.example.repository.UserRepository;

/**
 * Serwis uzytkownika — probka z mockowaniem DB.
 */
public class UserService {

    private final UserRepository userRepository;

    public UserService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public User getUserById(Long id) {
        if (id == null || id <= 0) {
            throw new IllegalArgumentException("Invalid user id");
        }
        return userRepository.findById(id);
    }

    public User createUser(String name, String email) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("Name is required");
        }
        User user = new User(name, email);
        return userRepository.save(user);
    }

    public boolean deleteUser(Long id) {
        return userRepository.deleteById(id);
    }
}
