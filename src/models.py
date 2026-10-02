from datetime import date, time
from typing import List, Optional
from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, String, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user_id
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_remind_offset: Mapped[int] = mapped_column(Integer, default=15)  # В минутах

    schedules: Mapped[List["Schedule"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Пн, 1=Вт, ..., 6=Вс
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    remind_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Override настроек

    user: Mapped["User"] = relationship(back_populates="schedules")
    homeworks: Mapped[List["Homework"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
    )


class Homework(Base):
    __tablename__ = "homeworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedules.id"))
    text: Mapped[str] = mapped_column(String)
    due_date: Mapped[date] = mapped_column(Date)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    schedule: Mapped["Schedule"] = relationship(back_populates="homeworks")