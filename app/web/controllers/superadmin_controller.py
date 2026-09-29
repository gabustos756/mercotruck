from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.auth import get_current_superadmin_web
from app.core.security import get_password_hash
from app.domain.models.user import User, UserRole
from app.domain.models.company import Company, PlanTier, SubscriptionStatus
from app.domain.models.truck import CompanyTruck, TruckType, TruckStatus
from app.domain.models.demo_request import DemoRequest, DemoStatus
from app.domain.models.tariff import MercotruckTariff
from app.web.jinja import templates

router = APIRouter(prefix="/superadmin", tags=["Superadmin crossTruck"])

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def superadmin_dashboard(
    request: Request,
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Dashboard principal del Superadmin de crossTruck."""
    # Métricas clave
    companies_q = await db.execute(select(Company).order_by(Company.created_at.desc()))
    companies = companies_q.scalars().all()
    
    total_companies = len(companies)
    active_companies = sum(1 for c in companies if c.subscription_status == SubscriptionStatus.ACTIVE)
    
    trucks_count_q = await db.execute(select(func.count(CompanyTruck.id)))
    total_trucks = trucks_count_q.scalar() or 0
    
    demos_q = await db.execute(select(DemoRequest).order_by(DemoRequest.created_at.desc()))
    all_demos = demos_q.scalars().all()
    pending_demos = [d for d in all_demos if d.status == DemoStatus.NUEVO]

    users_count_q = await db.execute(select(func.count(User.id)))
    total_users = users_count_q.scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="superadmin/dashboard.html",
        context={
            "current_user": current_user,
            "companies": companies,
            "total_companies": total_companies,
            "active_companies": active_companies,
            "total_trucks": total_trucks,
            "total_users": total_users,
            "demos": all_demos[:5],
            "pending_demos_count": len(pending_demos),
            "plans": [p.value for p in PlanTier]
        }
    )

@router.get("/companies", response_class=HTMLResponse)
async def list_companies(
    request: Request,
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Lista de todas las empresas clientes registradas."""
    query = (
        select(Company)
        .options(selectinload(Company.users), selectinload(Company.trucks))
        .order_by(Company.created_at.desc())
    )
    res = await db.execute(query)
    companies = res.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="superadmin/companies.html",
        context={
            "current_user": current_user,
            "companies": companies,
            "plans": [p.value for p in PlanTier],
            "statuses": [s.value for s in SubscriptionStatus]
        }
    )

@router.post("/companies", response_class=HTMLResponse)
async def create_company(
    request: Request,
    name: str = Form(...),
    business_name: Optional[str] = Form(None),
    cuit_rut: Optional[str] = Form(None),
    country: str = Form("Argentina"),
    contact_email: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    plan_tier: str = Form("PRO"),
    max_trucks: int = Form(50),
    max_users: int = Form(5),
    notes: Optional[str] = Form(None),
    # Usuario administrador inicial opcional
    admin_name: Optional[str] = Form(None),
    admin_email: Optional[str] = Form(None),
    admin_password: Optional[str] = Form(None),
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Crea una nueva empresa transportista y opcionalmente su usuario ADMIN."""
    company = Company(
        name=name.strip(),
        business_name=business_name.strip() if business_name else None,
        cuit_rut=cuit_rut.strip() if cuit_rut else None,
        country=country.strip(),
        contact_email=contact_email.strip() if contact_email else None,
        contact_phone=contact_phone.strip() if contact_phone else None,
        plan_tier=PlanTier(plan_tier),
        subscription_status=SubscriptionStatus.ACTIVE,
        max_trucks=max_trucks,
        max_users=max_users,
        notes=notes.strip() if notes else None
    )
    db.add(company)
    await db.flush()

    if admin_email and admin_password:
        hashed = get_password_hash(admin_password)
        new_admin = User(
            company_id=company.id,
            email=admin_email.strip().lower(),
            full_name=admin_name.strip() if admin_name else f"Admin {company.name}",
            hashed_password=hashed,
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(new_admin)

    await db.commit()
    return RedirectResponse(url=f"/superadmin/companies/{company.id}?created=1", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/companies/{company_id}", response_class=HTMLResponse)
async def company_detail(
    request: Request,
    company_id: int,
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Detalle de una empresa cliente: datos, flota de camiones, usuarios y tarifas."""
    query = (
        select(Company)
        .options(
            selectinload(Company.users),
            selectinload(Company.trucks),
            selectinload(Company.tariffs)
        )
        .where(Company.id == company_id)
    )
    res = await db.execute(query)
    company = res.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    return templates.TemplateResponse(
        request=request,
        name="superadmin/company_detail.html",
        context={
            "current_user": current_user,
            "company": company,
            "plans": [p.value for p in PlanTier],
            "statuses": [s.value for s in SubscriptionStatus],
            "truck_types": [t.value for t in TruckType],
            "truck_statuses": [ts.value for ts in TruckStatus]
        }
    )

@router.post("/companies/{company_id}/status")
async def update_company_status(
    company_id: int,
    subscription_status: str = Form(...),
    plan_tier: str = Form(...),
    max_trucks: int = Form(50),
    max_users: int = Form(5),
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Actualiza la suscripción y límites de la empresa."""
    res = await db.execute(select(Company).where(Company.id == company_id))
    company = res.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    company.subscription_status = SubscriptionStatus(subscription_status)
    company.plan_tier = PlanTier(plan_tier)
    company.max_trucks = max_trucks
    company.max_users = max_users
    await db.commit()

    return RedirectResponse(url=f"/superadmin/companies/{company_id}?updated=1", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/companies/{company_id}/users")
async def create_company_user(
    company_id: int,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("COMMERCIAL"),
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Crea un usuario para una empresa cliente."""
    res = await db.execute(select(Company).where(Company.id == company_id))
    company = res.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    hashed = get_password_hash(password)
    user = User(
        company_id=company.id,
        full_name=full_name.strip(),
        email=email.strip().lower(),
        hashed_password=hashed,
        role=UserRole(role),
        is_active=True
    )
    db.add(user)
    await db.commit()

    return RedirectResponse(url=f"/superadmin/companies/{company_id}?user_created=1", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/companies/{company_id}/trucks")
async def create_company_truck(
    company_id: int,
    plate_number: str = Form(...),
    truck_type: str = Form("SIDER"),
    brand_model: Optional[str] = Form(None),
    model_year: Optional[int] = Form(None),
    driver_name: Optional[str] = Form(None),
    driver_phone: Optional[str] = Form(None),
    current_city: Optional[str] = Form(None),
    status_val: str = Form("DISPONIBLE"),
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Agrega un camión a la flota de la empresa."""
    truck = CompanyTruck(
        company_id=company_id,
        plate_number=plate_number.strip().upper(),
        truck_type=TruckType(truck_type),
        brand_model=brand_model.strip() if brand_model else None,
        model_year=model_year,
        driver_name=driver_name.strip() if driver_name else None,
        driver_phone=driver_phone.strip() if driver_phone else None,
        current_city=current_city.strip() if current_city else None,
        status=TruckStatus(status_val)
    )
    db.add(truck)
    await db.commit()

    return RedirectResponse(url=f"/superadmin/companies/{company_id}?truck_created=1", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/demos", response_class=HTMLResponse)
async def list_demos(
    request: Request,
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Listado y gestión de solicitudes de demo recibidas desde la landing page."""
    res = await db.execute(select(DemoRequest).order_by(DemoRequest.created_at.desc()))
    demos = res.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="superadmin/demos.html",
        context={
            "current_user": current_user,
            "demos": demos,
            "statuses": [s.value for s in DemoStatus]
        }
    )

@router.post("/demos/{demo_id}/convert")
async def convert_demo_to_company(
    demo_id: int,
    default_password: str = Form("CrossTruck2026!"),
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Convierte una solicitud de demo directamente en cliente activo y crea su acceso."""
    res = await db.execute(select(DemoRequest).where(DemoRequest.id == demo_id))
    demo = res.scalar_one_or_none()
    if not demo:
        raise HTTPException(status_code=404, detail="Solicitud de demo no encontrada")

    # 1. Crear la empresa
    company = Company(
        name=demo.company_name,
        business_name=demo.company_name,
        contact_email=demo.email,
        contact_phone=demo.phone,
        plan_tier=PlanTier.TRIAL,
        subscription_status=SubscriptionStatus.TRIAL,
        notes=f"Convertido desde solicitud de demo. Corredor de interés: {demo.corridor_interest or 'No especificado'}. Flota: {demo.fleet_size or 'N/A'}"
    )
    db.add(company)
    await db.flush()

    # 2. Crear el usuario Administrador
    hashed = get_password_hash(default_password)
    admin_user = User(
        company_id=company.id,
        email=demo.email.strip().lower(),
        full_name=demo.contact_name.strip(),
        hashed_password=hashed,
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(admin_user)

    # 3. Marcar demo como CONVERTIDO
    demo.status = DemoStatus.CONVERTIDO
    demo.assigned_admin = current_user.full_name

    await db.commit()

    return RedirectResponse(url=f"/superadmin/companies/{company.id}?converted=1", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/demos/{demo_id}/status")
async def update_demo_status(
    demo_id: int,
    status_val: str = Form(...),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(get_current_superadmin_web),
    db: AsyncSession = Depends(get_db)
):
    """Actualiza el estado de la solicitud de demo."""
    res = await db.execute(select(DemoRequest).where(DemoRequest.id == demo_id))
    demo = res.scalar_one_or_none()
    if not demo:
        raise HTTPException(status_code=404, detail="Demo no encontrada")

    demo.status = DemoStatus(status_val)
    if notes:
        demo.notes = notes.strip()
    await db.commit()

    return RedirectResponse(url="/superadmin/demos?updated=1", status_code=status.HTTP_303_SEE_OTHER)
