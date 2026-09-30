<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreUserRequest;
use App\Http\Resources\UserResource;
use App\Services\UserService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class UserController extends Controller
{
    public function __construct(
        private UserService $userService,
    ) {
    }

    #[Route(path: '/users', methods: ['GET'])]
    public function index(Request $request): JsonResponse
    {
        $users = $this->userService->list();
        return response()->json(UserResource::collection($users));
    }

    #[Route(path: '/users/{id}', methods: ['GET'])]
    public function show(int $id): JsonResponse
    {
        $user = $this->userService->find($id);
        return response()->json(new UserResource($user));
    }

    #[Route(path: '/users', methods: ['POST'])]
    public function store(StoreUserRequest $request): JsonResponse
    {
        $user = $this->userService->create($request->validated());
        return response()->json(new UserResource($user), 201);
    }
}
