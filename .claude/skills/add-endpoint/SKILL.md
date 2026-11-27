---
name: add-endpoint
description: Step-by-step procedure for adding a new backend endpoint or feature to our FastAPI app (new resource, route, DB table, service method or query). Use this whenever the task adds something new under backend/app/features/, even if the request doesn't say "endpoint", e.g. "save the user's searches", "the frontend needs a list of X", "store the classification results", "add a summary route".
---

# Adding an endpoint or feature

The architecture rules (layers, model types, async, errors) are in CLAUDE.md. This skill is the procedure for applying them when you add something new.

## 1. Start from the reference

Read `app/features/conversations/` before writing anything, and copy its structure, naming and style. Copying a working example produces more consistent code than following rules from memory. If the reference and CLAUDE.md disagree, tell the user, because one of them is out of date.

Check whether the feature already exists. A new route on an existing feature means editing its files, not creating a new folder.

## 2. Files

```
app/features/<feature>/
  models.py       XORM
  schemas.py      X, RequestXCreate, RequestXUpdate, ResponseX (only the ones you need)
  repository.py   XRepository(BaseRepository[XORM, X])
  service.py
  dependencies.py get_x_repo → get_x_service → XServiceDep
  controller.py
```

## 3. Steps, in order

1. **ORM model** in `models.py`, then a migration: `alembic revision --autogenerate -m "..."`. Read the generated file before committing it; autogenerate misses things such as pgvector columns, renames and server defaults. Update `docs/database.md` (table, columns, diagram) in the same change.
2. **Schemas** in `schemas.py`. Add only the request models for endpoints that actually exist.
3. **Repository:** inherit from `BaseRepository`. Add only feature-specific queries, and don't re-implement `get_by_id` / `create` / `list` / `delete`. If the domain model includes relationships, eager-load them with `selectinload`. If two writes must succeed or fail together, write one method that does both and commits once.
4. **Service:** the logic, raising `core/errors.py` exceptions.
5. **Dependencies** in `dependencies.py`: provider functions plus an `XServiceDep` alias. If the service needs another feature's service, inject it here. For endpoints that take a resource ID, add an ownership dependency `get_owned_x(x_id, user) -> X` that raises `NotFoundError`.
6. **Controller:** use the protected router (`dependencies=[Depends(require_user)]`); put an endpoint on `public_router` only if it really must be public, and say why. Call one service method and map to the response model:
   ```python
   @router.post("", response_model=ResponseConversation, status_code=201)
   async def create_conversation(
       body: RequestConversationCreate, user: CurrentUserDep, service: ConversationServiceDep
   ) -> ResponseConversation:
       """Start a new conversation."""
       conversation = await service.create_conversation(body, owner_id=user.id)
       return _conversation_response(conversation)
   ```
7. **Register the router** in `app/main.py`.
8. **Tests:**
   - Add a factory `make_<resource>(session, **overrides)` to `tests/factories.py` that goes through the repository.
   - If the feature has its own logic (conditions, calculations, parsing), unit-test that function.
   - If the feature is on the demo path, add to `tests/smoke/`. Change an existing smoke test only together with the behaviour it pins, and name it in the PR.
9. **Run the checks** (`ruff format --check`, `ruff check`, `pyright`, `lint-imports`, `pytest`). Don't report the task as done until they pass. While agents work unattended, these checks are the only review.

## Done checklist

- [ ] Structure matches `features/conversations/`
- [ ] `XORM` is used only in `repository.py`, and `ResponseX` only in `controller.py`
- [ ] No sync clients or blocking calls in async code
- [ ] Migration reviewed
- [ ] Router registered
- [ ] Checks pass
