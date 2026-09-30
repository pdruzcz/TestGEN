<?php
// Serwis użytkowników — przykład kodu PHP do generowania testów PHPUnit/Pest (Story 1.55).

declare(strict_types=1);

namespace App\Services;

final class UserService
{
    /** @var array<string, array{username: string, email: string, active: bool}> */
    private array $users = [];

    /** Rzuca InvalidArgumentException dla nazwy krótszej niż 3 znaki. */
    public function createUser(string $username, string $email): string
    {
        if (strlen($username) < 3) {
            throw new \InvalidArgumentException('Nazwa użytkownika za krótka');
        }
        $this->users[$username] = ['username' => $username, 'email' => $email, 'active' => true];

        return $username;
    }

    public function deactivateUser(string $username): bool
    {
        if (!isset($this->users[$username])) {
            return false;
        }
        $this->users[$username]['active'] = false;

        return true;
    }

    public function isActive(string $username): bool
    {
        return isset($this->users[$username]) && $this->users[$username]['active'];
    }
}
