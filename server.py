import asyncio
import hashlib
import secrets
import json
import re
from datetime import datetime
from sqlalchemy import desc

from database import *

session = get_session()


def register(request):
    user = session.query(User).filter(User.username == request['username']).first()
    if user:
        raise Exception("Этот логин уже кто-то занял =(")
    if not re.match(r"[\w_]{3,16}", request['username']):
        raise Exception("Недопустимый логин. Только буквы, цифры и подчеркивания. Допустимая длина 3-16 символов")
    if not re.match(r".{3,16}", request['password']):
        raise Exception("Слабый пароль. Допустимая длина 3-16 символов")

    user = User(
        username=request['username'],
        password=encrypt_password(request['password']),
        token=generate_token()
    )
    session.add(user)
    return user


def login(request):
    user = session.query(User).filter(User.username == request['username']).first()
    if not user:
        raise Exception("Пользователь не найден")
    if user.password != encrypt_password(request['password']):
        raise Exception("Неверный пароль")

    user.token = generate_token()

    return user


def get_messages(request, user):
    if not user:
        raise PermissionError('Необходима авторизация')
    if request['token'] == user.token:
        raw_messages = session.query(Message) \
            .filter(Message.id > request['offset_id']) \
            .order_by(desc(Message.id)).limit(50).all()
        messages = [{'id': msg.id, 'msg': msg.text, 'user': msg.user.username} for msg in raw_messages[::-1]]
        return json.dumps(messages)
    else:
        raise PermissionError("Неверный токен")


def send_message(request, user):
    if not user:
        raise PermissionError('Необходима авторизация')
    if request['token'] == user.token:
        message = Message(text=request['message'], user=user)
        session.add(message)
        return "OK"
    else:
        raise PermissionError("Неверный токен")


def generate_token():
    return secrets.token_hex(16)


def encrypt_password(password):
    return hashlib.md5(password.encode()).hexdigest()


class Server:

    def __enter__(self):
        self.server = None
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            print(f'Получено исключение: {exc_type} {exc_value}')
            print(traceback)
        if self.server and not self.server.is_serving():
            self.server.close()
        return True

    async def start(self):
        self.server = await asyncio.start_server(self.serve_client, '127.0.0.1', 501)
        await self.server.serve_forever()

    async def serve_client(self, reader, writer):
        user = None

        def handle_request(request):
            nonlocal user

            try:
                success = True
                if request['route'] == 'get_messages':
                    message = get_messages(request, user)
                elif request['route'] == 'send_message':
                    message = send_message(request, user)
                elif request['route'] == 'register':
                    user = register(request)
                    message = "Пользователь успешно создан!"
                elif request['route'] == 'login':
                    user = login(request)
                    message = "Пользователь успешно вошел!"
                else:
                    raise Exception("Неизвестный route: " + request['route'])

            except Exception as e:
                success = False
                message = str(e)

            return {
                'success': success,
                'message': message,
                'token': user.token if user else ""
            }

        async def read_request():
            request = bytearray()
            try:
                while True:
                    chunk = await reader.read(64)
                    if not chunk:
                        break

                    request += chunk
                    if b'\0' in request:
                        return json.loads(request.replace(b'\0', b'').decode())
            except ConnectionResetError:
                pass

            return None

        async def write_response(response):
            writer.write(json.dumps(response).encode() + b'\0')
            await writer.drain()

        while True:
            request = await read_request()
            if request:
                response = handle_request(request)
                if request['route'] != 'send_message':
                    await write_response(response)
            else:
                break


async def main():
    with Server() as server:
        await server.start()


if __name__ == '__main__':
    asyncio.run(main())
