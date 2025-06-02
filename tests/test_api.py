import asyncio

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.database.models import Base, UsersORM, GoodsORM
from src.database.session import get_db
from src.main import app
from src.security import get_password_hash

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL)

async_session_for_test = async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    # Создаем event loop для сессии тестов (нужно для pytest-asyncio)
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    # Создаем таблицы перед тестами
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # После всех тестов таблицы удалить (если нужно)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async_client = TestClient(app)


@pytest.fixture()
def override_get_db_fixture():
    async def override():
        async with async_session_for_test() as session:
            yield session

    return override


@pytest.fixture(autouse=True)
def set_db_override(override_get_db_fixture):
    app.dependency_overrides[get_db] = override_get_db_fixture
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_goods():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/goods/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_register_and_login():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Регистрация нового пользователя
        user_data = {"username": "testuser", "password": "testpassword"}
        response = await client.post("/register", json=user_data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Пользователь зарегистрирован"}

        # Попытка повторной регистрации с тем же username - ошибка 400
        response = await client.post("/register", json=user_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "уже существует" in response.json()["detail"]

        # Успешный вход
        login_data = {"username": "testuser", "password": "testpassword"}
        response = await client.post(
            "/login",
            data=login_data,  # OAuth2PasswordRequestForm требует form-data, не json
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == status.HTTP_200_OK
        json_resp = response.json()
        assert "access_token" in json_resp
        assert json_resp["token_type"] == "bearer"

        # Ошибка входа — неправильный пароль
        bad_login_data = {"username": "testuser", "password": "wrongpassword"}
        response = await client.post(
            "/login",
            data=bad_login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_read_your_goods(override_get_db_fixture):
    async for db in override_get_db_fixture():
        # Создаём тестового пользователя
        hashed_password = get_password_hash("testpass")
        user = UsersORM(username="owner", hashed_password=hashed_password)
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Добавляем пару товаров от этого пользователя
        good1 = GoodsORM(
            title="Товар 1",
            description="описание 1",
            category="транспорт",
            user_id=user.id,
        )
        good2 = GoodsORM(
            title="Товар 2",
            description="описание 2",
            category="игрушка",
            user_id=user.id,
        )
        db.add_all([good1, good2])
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Логин
        response = await client.post(
            "/login",
            data={"username": "owner", "password": "testpass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]

        # Запрос своих товаров
        response = await client.get(
            "/goods/mine", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["title"] == "Товар 1"
        assert data[1]["title"] == "Товар 2"


@pytest.mark.asyncio
async def test_create_goods():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Регистрация
        await client.post(
            "/register", json={"username": "owner", "password": "testpass"}
        )

        # Логин
        response = await client.post(
            "/login",
            data={"username": "owner", "password": "testpass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        good_data = {
            "title": "string",
            "description": "string",
            "image_url": "string",
            "category": "string",
            "condition": "новый",
        }
        # Запрос своих товаров с токеном в заголовке
        response = await client.post("/goods/", json=good_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "товар добавлен"
        assert data["goods"]["title"] == good_data["title"]
        assert data["goods"]["category"] == good_data["category"]


@pytest.mark.asyncio
async def test_get_one_good():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Регистрация
        await client.post(
            "/register", json={"username": "owner", "password": "testpass"}
        )

        # Логин
        response = await client.post(
            "/login",
            data={"username": "owner", "password": "testpass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Добавляем товар
        good_data = {
            "title": "Test Good",
            "description": "Get test description",
            "image_url": "http://example.com/image.jpg",
            "category": "get_test_category",
            "condition": "новый",
        }
        create_resp = await client.post("/goods/", json=good_data, headers=auth_headers)
        assert create_resp.status_code == 200
        good_id = create_resp.json()["goods"]["id"]

        # Получаем этот товар по ID
        get_resp = await client.get(f"/goods/{good_id}")
        assert get_resp.status_code == 200
        good = get_resp.json()
        assert good["title"] == good_data["title"]
        assert good["description"] == good_data["description"]


@pytest.mark.asyncio
async def test_edit_good():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Регистрация
        await client.post(
            "/register", json={"username": "owner", "password": "testpass"}
        )

        # Логин
        response = await client.post(
            "/login",
            data={"username": "owner", "password": "testpass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Создание товара
        good_data = {
            "title": "Original Title",
            "description": "Original description",
            "image_url": "http://example.com/original.jpg",
            "category": "original_category",
            "condition": "б/у",
        }
        create_resp = await client.post("/goods/", json=good_data, headers=auth_headers)
        assert create_resp.status_code == 200
        good_id = create_resp.json()["goods"]["id"]

        # Обновление товара
        update_data = {"title": "Updated Title", "description": "Updated description"}
        patch_resp = await client.patch(
            f"/goods/{good_id}", json=update_data, headers=auth_headers
        )
        assert patch_resp.status_code == 200

        updated_good = patch_resp.json()
        assert updated_good["title"] == update_data["title"]
        assert updated_good["description"] == update_data["description"]
        assert updated_good["category"] == good_data["category"]  # не изменяли


@pytest.mark.asyncio
async def test_delete_good():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Регистрация
        await client.post(
            "/register", json={"username": "owner", "password": "testpass"}
        )

        # Логин
        response = await client.post(
            "/login",
            data={"username": "owner", "password": "testpass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Создание товара
        good_data = {
            "title": "Original Title",
            "description": "Original description",
            "image_url": "http://example.com/original.jpg",
            "category": "original_category",
            "condition": "б/у",
        }
        create_resp = await client.post("/goods/", json=good_data, headers=auth_headers)
        assert create_resp.status_code == 200
        good_id = create_resp.json()["goods"]["id"]

        # Удаление товара
        delete_resp = await client.delete(f"/goods/{good_id}", headers=auth_headers)
        assert delete_resp.status_code == 200
        assert delete_resp.json()["message"] == "Объявление успешно удалено"

        # Повторное удаление (товара уже нет)
        delete_again = await client.delete(f"/goods/{good_id}", headers=auth_headers)
        assert delete_again.status_code == 404
        assert delete_again.json()["detail"] == "Объявление не найдено"


@pytest.mark.asyncio
async def test_create_trade_offer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Регистрация и логин отправителя
        sender = {"username": "sender_user", "password": "senderpass"}
        await client.post("/register", json=sender)
        sender_login = await client.post(
            "/login",
            data=sender,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        sender_token = sender_login.json()["access_token"]
        sender_headers = {"Authorization": f"Bearer {sender_token}"}

        # Регистрация и логин получателя
        receiver = {"username": "receiver_user", "password": "receiverpass"}
        await client.post("/register", json=receiver)
        receiver_login = await client.post(
            "/login",
            data=receiver,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        receiver_token = receiver_login.json()["access_token"]
        receiver_headers = {"Authorization": f"Bearer {receiver_token}"}

        # Получатель создаёт объявление
        receiver_good = {
            "title": "Receiver Item",
            "description": "Receiver's good",
            "image_url": "http://example.com/item1.jpg",
            "category": "book",
            "condition": "новый",
        }
        create_receiver_good = await client.post(
            "/goods/", json=receiver_good, headers=receiver_headers
        )
        ad_receiver_id = create_receiver_good.json()["goods"]["id"]

        # Отправитель создаёт своё объявление
        sender_good = {
            "title": "Sender Item",
            "description": "Sender's good",
            "image_url": "http://example.com/item2.jpg",
            "category": "game",
            "condition": "б/у",
        }
        create_sender_good = await client.post(
            "/goods/", json=sender_good, headers=sender_headers
        )
        ad_sender_id = create_sender_good.json()["goods"]["id"]

        # Отправка предложения обмена
        trade_data = {
            "ad_sender_id": ad_sender_id,
            "ad_receiver_id": ad_receiver_id,
            "comment": "Хотел бы обменяться",
        }
        response = await client.post(
            "/offers/", json=trade_data, headers=sender_headers
        )
        assert response.status_code == 200

        trade = response.json()
        assert trade["ad_sender_id"] == ad_sender_id
        assert trade["ad_receiver_id"] == ad_receiver_id
        assert trade["comment"] == "Хотел бы обменяться"
        assert trade["status"] == "ожидает"


@pytest.mark.asyncio
async def test_trade_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sender = {"username": "sender2", "password": "pass"}
        receiver = {"username": "receiver2", "password": "pass"}

        await client.post("/register", json=sender)
        await client.post("/register", json=receiver)

        sender_login = await client.post(
            "/login",
            data=sender,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        receiver_login = await client.post(
            "/login",
            data=receiver,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        sender_token = sender_login.json()["access_token"]
        receiver_token = receiver_login.json()["access_token"]

        sender_headers = {"Authorization": f"Bearer {sender_token}"}
        receiver_headers = {"Authorization": f"Bearer {receiver_token}"}

        # Создаём объявления
        sender_good = {
            "title": "Sender2 Good",
            "description": "A good from sender2",
            "image_url": "http://example.com/s2.jpg",
            "category": "book",
            "condition": "новый",
        }
        receiver_good = {
            "title": "Receiver2 Good",
            "description": "A good from receiver2",
            "image_url": "http://example.com/r2.jpg",
            "category": "game",
            "condition": "новый",
        }

        r1 = await client.post("/goods/", json=sender_good, headers=sender_headers)
        r2 = await client.post("/goods/", json=receiver_good, headers=receiver_headers)

        ad_sender_id = r1.json()["goods"]["id"]
        ad_receiver_id = r2.json()["goods"]["id"]

        # Создаём предложение обмена
        trade_payload = {
            "ad_sender_id": ad_sender_id,
            "ad_receiver_id": ad_receiver_id,
            "comment": "Интересует обмен",
        }
        resp = await client.post("/offers/", json=trade_payload, headers=sender_headers)
        assert resp.status_code == 200, resp.text

        # Получение списка сделок отправителем
        response = await client.get("/offers/", headers=sender_headers)
        assert response.status_code == 200

        trades = response.json()
        assert isinstance(trades, list)
        assert len(trades) >= 1
        trade = trades[0]
        assert trade["ad_sender_id"] == ad_sender_id
        assert trade["ad_receiver_id"] == ad_receiver_id
        assert trade["status"] == "ожидает"


@pytest.mark.asyncio
async def test_change_trade_status():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Регистрируем двух пользователей
        sender = {"username": "sender3", "password": "pass"}
        receiver = {"username": "receiver3", "password": "pass"}

        await client.post("/register", json=sender)
        await client.post("/register", json=receiver)

        # Логиним двух пользователей
        sender_login = await client.post(
            "/login",
            data=sender,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        receiver_login = await client.post(
            "/login",
            data=receiver,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        sender_token = sender_login.json()["access_token"]
        receiver_token = receiver_login.json()["access_token"]

        sender_headers = {"Authorization": f"Bearer {sender_token}"}
        receiver_headers = {"Authorization": f"Bearer {receiver_token}"}

        # Создаём объявления для отправителя и получателя
        sender_good = {
            "title": "Sender3 Good",
            "description": "Good from sender3",
            "image_url": "http://example.com/s3.jpg",
            "category": "book",
            "condition": "новый",
        }
        receiver_good = {
            "title": "Receiver3 Good",
            "description": "Good from receiver3",
            "image_url": "http://example.com/r3.jpg",
            "category": "game",
            "condition": "новый",
        }

        r1 = await client.post("/goods/", json=sender_good, headers=sender_headers)
        r2 = await client.post("/goods/", json=receiver_good, headers=receiver_headers)

        ad_sender_id = r1.json()["goods"]["id"]
        ad_receiver_id = r2.json()["goods"]["id"]

        # Создаём предложение обмена (trade)
        trade_payload = {
            "ad_sender_id": ad_sender_id,
            "ad_receiver_id": ad_receiver_id,
            "comment": "Хочу обменять",
        }
        trade_resp = await client.post(
            "/offers/", json=trade_payload, headers=sender_headers
        )
        assert trade_resp.status_code == 200
        trade = trade_resp.json()
        offer_id = trade["id"]

        # Получаем текущее состояние предложения (должно быть 'ожидает')
        assert trade["status"] == "ожидает"

        # Меняем статус предложения на 'принята' от имени получателя (receiver)
        update_payload = {"status": "принята"}

        patch_resp = await client.patch(
            f"/offers/{offer_id}", json=update_payload, headers=receiver_headers
        )
        assert patch_resp.status_code == 200

        updated_trade = patch_resp.json()
        assert updated_trade["id"] == offer_id
        assert updated_trade["status"] == "принята"

        # Проверяем, что нельзя изменить статус от имени не получателя (sender)
        forbidden_resp = await client.patch(
            f"/offers/{offer_id}", json={"status": "отклонена"}, headers=sender_headers
        )
        assert forbidden_resp.status_code == 403
