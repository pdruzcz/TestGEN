<?php

namespace App\Enums;

enum Status: string
{
    case Active = 'active';
    case Disabled = 'disabled';
    case Pending = 'pending';

    public function label(): string
    {
        return match ($this) {
            self::Active => 'Active',
            self::Disabled => 'Disabled',
            self::Pending => 'Pending',
        };
    }

    public static function fromValue(string $value): self
    {
        foreach (self::cases() as $case) {
            if ($case->value === $value) {
                return $case;
            }
        }
        throw new \ValueError("Unknown status: $value");
    }
}
