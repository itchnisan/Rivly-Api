from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.catch import Catch
from app.models.favorite_spot import FavoriteSpot
from app.models.species import Species
from app.models.spot import Spot, WaterType
from app.models.user import User


async def test_create_user_sets_id_and_created_at(db_session):
    user = User(email="alice@example.com", username="alice", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()

    assert user.id is not None
    assert user.created_at is not None


async def test_user_email_must_be_unique(db_session):
    db_session.add(User(email="dup@example.com", username="u1", hashed_password="x"))
    await db_session.commit()

    db_session.add(User(email="dup@example.com", username="u2", hashed_password="x"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_user_username_must_be_unique(db_session):
    db_session.add(User(email="a@example.com", username="dupname", hashed_password="x"))
    await db_session.commit()

    db_session.add(User(email="b@example.com", username="dupname", hashed_password="x"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_create_spot_with_water_type(db_session):
    user = User(email="owner@example.com", username="owner", hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    spot = Spot(
        name="Lac de Serre-Ponçon",
        latitude=44.5,
        longitude=6.3,
        water_type=WaterType.LAKE,
        created_by=user.id,
    )
    db_session.add(spot)
    await db_session.commit()

    assert spot.id is not None
    assert spot.water_type == WaterType.LAKE


async def test_user_spots_relationship(db_session):
    user = User(email="creator@example.com", username="creator", hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    spot = Spot(
        name="Rivière du Moulin",
        latitude=45.0,
        longitude=5.0,
        water_type=WaterType.RIVER,
        created_by=user.id,
    )
    db_session.add(spot)
    await db_session.commit()

    result = await db_session.execute(
        select(User).where(User.id == user.id).options(selectinload(User.spots))
    )
    fetched = result.scalar_one()
    assert len(fetched.spots) == 1
    assert fetched.spots[0].id == spot.id


async def test_create_species_with_season(db_session):
    species = Species(
        name="Esox lucius",
        common_name="Brochet",
        legal_size_cm=60,
        open_season_start=date(2026, 5, 1),
        open_season_end=date(2027, 1, 31),
    )
    db_session.add(species)
    await db_session.commit()

    assert species.id is not None


async def test_create_catch_with_json_conditions(db_session):
    user = User(email="angler@example.com", username="angler", hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    spot = Spot(
        name="Étang Nord", latitude=48.1, longitude=2.5, water_type=WaterType.POND, created_by=user.id
    )
    species = Species(name="Cyprinus carpio", common_name="Carpe")
    db_session.add_all([spot, species])
    await db_session.commit()

    catch = Catch(
        user_id=user.id,
        spot_id=spot.id,
        species_id=species.id,
        weight_g=3200,
        length_cm=62.5,
        caught_at=datetime(2026, 6, 1, 8, 30, tzinfo=timezone.utc),
        conditions={"weather": "cloudy", "water_temp_c": 18, "moon_phase": "waning"},
        notes="belle prise",
    )
    db_session.add(catch)
    await db_session.commit()

    result = await db_session.execute(select(Catch).where(Catch.id == catch.id))
    fetched = result.scalar_one()
    assert fetched.conditions["weather"] == "cloudy"
    assert fetched.conditions["water_temp_c"] == 18


async def test_favorite_spot_composite_key(db_session):
    user = User(email="fan@example.com", username="fan", hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    spot = Spot(
        name="Coin secret", latitude=1.0, longitude=1.0, water_type=WaterType.RIVER, created_by=user.id
    )
    db_session.add(spot)
    await db_session.commit()

    favorite = FavoriteSpot(user_id=user.id, spot_id=spot.id)
    db_session.add(favorite)
    await db_session.commit()

    result = await db_session.execute(
        select(FavoriteSpot).where(
            FavoriteSpot.user_id == user.id, FavoriteSpot.spot_id == spot.id
        )
    )
    assert result.scalar_one() is not None


async def test_favorite_spot_duplicate_raises(db_session):
    user = User(email="dupfan@example.com", username="dupfan", hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    spot = Spot(
        name="Coin secret 2", latitude=1.0, longitude=1.0, water_type=WaterType.RIVER, created_by=user.id
    )
    db_session.add(spot)
    await db_session.commit()

    db_session.add(FavoriteSpot(user_id=user.id, spot_id=spot.id))
    await db_session.commit()

    db_session.add(FavoriteSpot(user_id=user.id, spot_id=spot.id))
    with pytest.raises(IntegrityError):
        await db_session.commit()
