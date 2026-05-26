from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import passlib.hash as pbkdf2
from datetime import datetime

DATABASE_URL = ""

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserModel(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)

class ClassMemberModel(Base):
    __tablename__ = "class_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    teacher_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

class GradeModel(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    value = Column(Integer, nullable=False)
    date = Column(String, nullable=False)

class HomeworkModel(Base):
    __tablename__ = "homework"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    day_of_week = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    description = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

class UserRegister(BaseModel):
    username: str
    name: str
    password: str
    role: str

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    user_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None

class ClassMemberSchema(BaseModel):
    teacher_id: int
    student_id: int

class GradeRequest(BaseModel):
    student_id: int
    teacher_id: int
    value: int

class GradeResponse(BaseModel):
    id: int
    student_id: int
    teacher_id: int
    value: int
    date: str

    class Config:
        from_attributes = True

class HomeworkRequest(BaseModel):
    day_of_week: int
    subject: str
    description: str

class HomeworkResponse(BaseModel):
    id: int
    day_of_week: int
    subject: str
    description: str

    class Config:
        from_attributes = True

app = FastAPI(title="StudyFlow API")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register", response_model=UserResponse)
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    exists = db.query(UserModel).filter(UserModel.username == user.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="Этот юзернейм уже занят")
    
    hashed_password = pbkdf2.sha256.hash(user.password)
    new_user = UserModel(
        username=user.username,
        full_name=user.name,
        password_hash=hashed_password,
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login", response_model=UserResponse)
def login_user(user: UserRegister, db: Session = Depends(get_db)):
    db_user = db.query(UserModel).filter(UserModel.username == user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if not pbkdf2.sha256.verify(user.password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный пароль")
    return db_user

@app.get("/user/{id}", response_model=UserResponse)
def get_user_by_id(id: int, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user

@app.put("/users/update")
def update_profile(data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if data.username:
        exists = db.query(UserModel).filter(UserModel.username == data.username, UserModel.id != data.user_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Этот юзернейм уже занят")
        user.username = data.username
        
    if data.full_name:
        user.full_name = data.full_name
        
    if data.password:
        user.password_hash = pbkdf2.sha256.hash(data.password)
        
    db.commit()
    return {"message": "Профиль успешно обновлен"}

@app.get("/students/find", response_model=List[UserResponse])
def find_student_by_nickname(username: str, db: Session = Depends(get_db)):
    students = db.query(UserModel).filter(
        UserModel.username.ilike(f"%{username}%"),
        UserModel.role == "Ученик"
    ).all()
    return students

@app.post("/students/add")
def add_student_to_teacher(member: ClassMemberSchema, db: Session = Depends(get_db)):
    exists = db.query(ClassMemberModel).filter(
        ClassMemberModel.teacher_id == member.teacher_id,
        ClassMemberModel.student_id == member.student_id
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Этот ученик уже добавлен")
        
    new_member = ClassMemberModel(teacher_id=member.teacher_id, student_id=member.student_id)
    db.add(new_member)
    db.commit()
    return {"message": "Ученик успешно добавлен к учителю"}

@app.get("/students/my", response_model=List[UserResponse])
def get_my_students(teacher_id: int, db: Session = Depends(get_db)):
    links = db.query(ClassMemberModel).filter(ClassMemberModel.teacher_id == teacher_id).all()
    student_ids = [l.student_id for l in links]
    return db.query(UserModel).filter(UserModel.id.in_(student_ids)).all() if student_ids else []

@app.get("/students/my_teacher", response_model=UserResponse)
def get_my_teacher(student_id: int, db: Session = Depends(get_db)):
    link = db.query(ClassMemberModel).filter(ClassMemberModel.student_id == student_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="У вас пока нет учителя")
    return db.query(UserModel).filter(UserModel.id == link.teacher_id).first()

@app.delete("/teachers/delete_student/{student_id}")
def delete_student(student_id: int, teacher_id: int, db: Session = Depends(get_db)):
    link = db.query(ClassMemberModel).filter(
        ClassMemberModel.student_id == student_id,
        ClassMemberModel.teacher_id == teacher_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Связь не найдена")
    db.delete(link)
    db.commit()
    return {"message": "Ученик успешно удален"}

@app.post("/students/marks/add")
def add_grade(grade_request: GradeRequest, db: Session = Depends(get_db)):
    current_date = datetime.now().strftime("%d.%m.%Y")
    new_grade = GradeModel(
        student_id=grade_request.student_id,
        teacher_id=grade_request.teacher_id,
        value=grade_request.value,
        date=current_date
    )
    db.add(new_grade)
    db.commit()
    return {"message": "Оценка добавлена"}

@app.get("/students/marks/{student_id}", response_model=List[GradeResponse])
def get_student_marks(student_id: int, db: Session = Depends(get_db)):
    return db.query(GradeModel).filter(GradeModel.student_id == student_id).all()

@app.post("/homework/add", response_model=HomeworkResponse)
def add_homework(homework_data: HomeworkRequest, db: Session = Depends(get_db)):
    new_homework = HomeworkModel(
        day_of_week=homework_data.day_of_week,
        subject=homework_data.subject,
        description=homework_data.description
    )
    db.add(new_homework)
    db.commit()
    db.refresh(new_homework)
    return new_homework

@app.get("/homework/all", response_model=List[HomeworkResponse])
def get_all_homework(db: Session = Depends(get_db)):
    return db.query(HomeworkModel).all()

@app.delete("/students/marks/delete/{grade_id}")
def delete_grade(grade_id: int, db: Session = Depends(get_db)):

    grade = db.query(GradeModel).filter(GradeModel.id == grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Оценка не найдена")
    
    db.delete(grade)
    db.commit()
    return {"message": "Оценка успешно удалена"}
