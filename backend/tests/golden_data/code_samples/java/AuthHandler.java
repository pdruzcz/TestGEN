package com.example.auth;

import com.example.service.TokenService;
import com.example.repository.SessionRepository;

/**
 * Handler autoryzacji — probka z wieloma mockami.
 */
public class AuthHandler {

    private final TokenService tokenService;
    private final SessionRepository sessionRepository;

    public AuthHandler(TokenService tokenService, SessionRepository sessionRepository) {
        this.tokenService = tokenService;
        this.sessionRepository = sessionRepository;
    }

    public String authenticate(String username, String password) {
        if (username == null || password == null) {
            throw new IllegalArgumentException("Credentials required");
        }
        boolean valid = tokenService.validateCredentials(username, password);
        if (!valid) {
            throw new SecurityException("Invalid credentials");
        }
        String token = tokenService.generateToken(username);
        sessionRepository.saveSession(username, token);
        return token;
    }

    public boolean validateToken(String token) {
        if (token == null || token.isBlank()) {
            return false;
        }
        return tokenService.isTokenValid(token);
    }

    public void logout(String token) {
        sessionRepository.removeSession(token);
    }
}
