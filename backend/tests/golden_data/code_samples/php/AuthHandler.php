<?php
// Obsługa uwierzytelniania — przykład kodu PHP do generowania testów PHPUnit/Pest (Story 1.55).

declare(strict_types=1);

namespace App\Security;

final class AuthHandler
{
    private const MIN_PASSWORD_LENGTH = 8;

    /** @var array<string, string> */
    private array $sessions = [];

    /** Rzuca InvalidArgumentException dla hasła krótszego niż 8 znaków. */
    public function hashPassword(string $password): string
    {
        if (strlen($password) < self::MIN_PASSWORD_LENGTH) {
            throw new \InvalidArgumentException('Hasło za krótkie');
        }

        return password_hash($password, PASSWORD_ARGON2ID);
    }

    public function verifyPassword(string $password, string $hash): bool
    {
        return password_verify($password, $hash);
    }

    public function createSession(string $username): string
    {
        $token = bin2hex(random_bytes(16));
        $this->sessions[$token] = $username;

        return $token;
    }

    public function validateSession(string $token): ?string
    {
        return $this->sessions[$token] ?? null;
    }
}
