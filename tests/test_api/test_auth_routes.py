"""Tests for authentication routes"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from unittest.mock import AsyncMock, MagicMock

from seriesoftubes.api.main import app
from seriesoftubes.api.auth import get_password_hash, verify_password
from seriesoftubes.db import User, get_db


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    session = AsyncMock()
    
    # Mock the execute method
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    
    # Mock transaction methods
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    
    return session


@pytest.fixture
def client(mock_db_session):
    """Create test client with mocked database"""
    app.dependency_overrides[get_db] = lambda: mock_db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def existing_user():
    """Create an existing user for testing"""
    return User(
        id="existing-user-id",
        username="existinguser",
        email="existing@example.com",
        password_hash=get_password_hash("existingpass123"),
        is_active=True,
        is_admin=False,
        is_system=False,
    )


class TestAuthRoutes:
    """Test authentication routes"""
    
    def test_register_success(self, client, mock_db_session):
        """Test successful user registration"""
        # Setup
        registration_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepass123"
        }
        
        # Mock the refresh method to simulate database creating the user
        def mock_refresh(user):
            user.id = "new-user-id"
            user.is_admin = False
            user.is_active = True
            user.is_system = False
            
        mock_db_session.refresh.side_effect = mock_refresh
        
        # Execute
        response = client.post("/auth/register", json=registration_data)
        
        # Verify
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "password" not in data
        assert "password_hash" not in data
        
        # Verify database interaction
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
    def test_register_duplicate_username(self, client, mock_db_session, existing_user):
        """Test registration with duplicate username"""
        # Setup mock to return existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute.return_value = mock_result
        
        registration_data = {
            "username": "existinguser",
            "email": "different@example.com",
            "password": "securepass123"
        }
        
        # Execute
        response = client.post("/auth/register", json=registration_data)
        
        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["detail"]
        
    def test_register_invalid_email(self, client):
        """Test registration with invalid email"""
        registration_data = {
            "username": "newuser",
            "email": "not-an-email",
            "password": "securepass123"
        }
        
        response = client.post("/auth/register", json=registration_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
    def test_register_short_password(self, client):
        """Test registration with password too short"""
        registration_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "short"
        }
        
        response = client.post("/auth/register", json=registration_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
    def test_login_success(self, client, mock_db_session, existing_user):
        """Test successful login"""
        # Setup mock to return existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute.return_value = mock_result
        
        login_data = {
            "username": "existinguser",
            "password": "existingpass123"
        }
        
        # Execute
        response = client.post("/auth/login", json=login_data)
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
    def test_login_invalid_username(self, client, mock_db_session):
        """Test login with non-existent username"""
        login_data = {
            "username": "nonexistent",
            "password": "somepass123"
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Incorrect username or password"
        
    def test_login_invalid_password(self, client, mock_db_session, existing_user):
        """Test login with wrong password"""
        # Setup mock to return existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute.return_value = mock_result
        
        login_data = {
            "username": "existinguser",
            "password": "wrongpassword"
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Incorrect username or password"
        
    def test_login_inactive_user(self, client, mock_db_session):
        """Test login with inactive user"""
        # Create inactive user
        inactive_user = User(
            id="inactive-user-id",
            username="inactiveuser",
            email="inactive@example.com",
            password_hash=get_password_hash("somepass123"),
            is_active=False,
            is_admin=False,
            is_system=False,
        )
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inactive_user
        mock_db_session.execute.return_value = mock_result
        
        login_data = {
            "username": "inactiveuser",
            "password": "somepass123"
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Inactive user"
        
    def test_get_current_user(self, client, mock_db_session, existing_user):
        """Test getting current user info"""
        # Setup mock to return user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute.return_value = mock_result
        
        # First login to get token
        login_response = client.post("/auth/login", json={
            "username": "existinguser",
            "password": "existingpass123"
        })
        token = login_response.json()["access_token"]
        
        # Get current user
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "existinguser"
        assert data["email"] == "existing@example.com"
        
    def test_get_current_user_no_token(self, client):
        """Test getting current user without token"""
        response = client.get("/auth/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token"""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED