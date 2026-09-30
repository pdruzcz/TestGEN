<?php

namespace App\Repositories;

use App\Contracts\Cacheable;

interface UserRepository
{
    public function find(int $id): ?array;

    public function save(array $data): int;
}

trait LoggingTrait
{
    public function debug(string $message): void
    {
        error_log($message);
    }

    protected function log(string $level, string $message): void
    {
        error_log("[$level] $message");
    }
}

class DatabaseUserRepository implements UserRepository
{
    use LoggingTrait;

    public function find(int $id): ?array
    {
        if ($id <= 0) {
            return null;
        }
        return ['id' => $id];
    }

    public function save(array $data): int
    {
        $this->debug('Saving user');
        return count($data);
    }
}
