<?php

declare(strict_types=1);

namespace App\Model;

/**
 * Plain Old PHP Object — simple value object with typed properties and getters.
 */
final class User
{
    private string $name;
    private int $age;

    public function __construct(string $name, int $age)
    {
        $this->name = $name;
        $this->age = $age;
    }

    public function getName(): string
    {
        return $this->name;
    }

    public function getAge(): int
    {
        return $this->age;
    }

    public function isAdult(): bool
    {
        return $this->age >= 18;
    }
}
