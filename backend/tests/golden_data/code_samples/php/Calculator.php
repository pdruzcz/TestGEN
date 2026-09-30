<?php
// Prosty kalkulator — przykład kodu PHP do generowania testów PHPUnit/Pest (Story 1.55).

declare(strict_types=1);

namespace App;

final class Calculator
{
    /** @var float[] */
    private array $history = [];

    public function add(float $a, float $b): float
    {
        $result = $a + $b;
        $this->history[] = $result;

        return $result;
    }

    public function subtract(float $a, float $b): float
    {
        $result = $a - $b;
        $this->history[] = $result;

        return $result;
    }

    public function multiply(float $a, float $b): float
    {
        $result = $a * $b;
        $this->history[] = $result;

        return $result;
    }

    /** Rzuca InvalidArgumentException dla $b = 0. */
    public function divide(float $a, float $b): float
    {
        if ($b === 0.0) {
            throw new \InvalidArgumentException('Nie można dzielić przez zero');
        }
        $result = $a / $b;
        $this->history[] = $result;

        return $result;
    }

    public function reset(): void
    {
        $this->history = [];
    }

    public function getLast(): ?float
    {
        return $this->history !== [] ? $this->history[count($this->history) - 1] : null;
    }
}
