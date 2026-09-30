<?php

namespace Tests\Unit;

use PHPUnit\Framework\TestCase;

class UserTest extends TestCase
{
    private User $user;

    protected function setUp(): void
    {
        $this->user = new User('Alice', 30);
    }

    #[Test]
    public function it_returns_the_name(): void
    {
        $this->assertSame('Alice', $this->user->getName());
    }

    #[Test]
    public function it_detects_adults(): void
    {
        $this->assertTrue($this->user->isAdult());
    }

    public function generatorValues(): array
    {
        return [
            [18, true],
            [17, false],
        ];
    }
}
