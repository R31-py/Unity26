# -*- coding: utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, DateField, IntegerField, SelectField,
    BooleanField, TextAreaField, HiddenField,
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, Optional, NumberRange, ValidationError,
)


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Fjalëkalimi", validators=[DataRequired()])


class RegistrationForm(FlaskForm):
    # --- Llogaria ---
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField(
        "Fjalëkalimi",
        validators=[DataRequired(), Length(min=10, message="Të paktën 10 karaktere.")],
    )
    confirm_password = PasswordField(
        "Konfirmo fjalëkalimin",
        validators=[DataRequired(), EqualTo("password", message="Fjalëkalimet nuk përputhen.")],
    )

    # --- Informacion Personal ---
    first_name = StringField("Emri", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Mbiemri", validators=[DataRequired(), Length(max=100)])
    birth_date = DateField("Data e lindjes", validators=[DataRequired()], format="%Y-%m-%d")
    gender = SelectField(
        "Gjinia",
        choices=[("mashkull", "Mashkull"), ("femer", "Femër"), ("tjeter", "Preferoj të mos e them")],
        validators=[DataRequired()],
    )
    phone = StringField("Numri i telefonit", validators=[DataRequired(), Length(max=50)])
    address = StringField("Adresa", validators=[Optional(), Length(max=255)])
    city = StringField("Qyteti", validators=[DataRequired(), Length(max=100)])

    emergency_contact_name = StringField("Emri i personit (kontakt emergjence)",
                                          validators=[DataRequired(), Length(max=150)])
    emergency_contact_phone = StringField("Numri i telefonit (kontakt emergjence)",
                                           validators=[DataRequired(), Length(max=50)])

    # --- Përvoja në kamp ---
    attended_before = SelectField("A ke marrë pjesë më parë?", choices=[("po", "Po"), ("jo", "Jo")])
    times_attended = IntegerField("Sa herë ke marrë pjesë?", validators=[Optional(), NumberRange(min=0, max=50)])
    last_year_attended = IntegerField("Në cilin vit?", validators=[Optional(), NumberRange(min=2000, max=2100)])

    # --- Gjendja shëndetësore ---
    has_allergies = SelectField("A ke ndonjë alergji?", choices=[("po", "Po"), ("jo", "Jo")])
    allergies_description = TextAreaField("Përshkruaj alergjinë", validators=[Optional(), Length(max=1000)])
    health_notes = TextAreaField("Problem shëndetësor për organizatorët", validators=[Optional(), Length(max=2000)])
    takes_medication = SelectField("A merr medikament?", choices=[("po", "Po"), ("jo", "Jo")])
    medication_name = StringField("Cilin medikament?", validators=[Optional(), Length(max=255)])
    medication_instructions = TextAreaField("Udhëzime të veçanta", validators=[Optional(), Length(max=1000)])

    # --- Informacion shtesë ---
    dietary_requirement = SelectField(
        "Kërkesa ushqimore",
        choices=[("asnje", "Asnjë"), ("vegjetarian", "Vegjetarian"), ("vegan", "Vegan"),
                 ("pa_gluten", "Pa gluten"), ("tjeter", "Tjetër")],
    )
    dietary_other = StringField("Specifiko", validators=[Optional(), Length(max=255)])
    talent_description = TextAreaField("Talenti/aftësia", validators=[Optional(), Length(max=1000)])
    shirt_size = SelectField("Masa e bluzës", choices=[("S", "S"), ("M", "M"), ("L", "L"),
                                                        ("XL", "XL"), ("XXL", "XXL")])

    # --- Prind/Kujdestar (nëse < 18) ---
    guardian_name = StringField("Emri i prindit/kujdestarit", validators=[Optional(), Length(max=150)])
    guardian_phone = StringField("Numri i telefonit (prind)", validators=[Optional(), Length(max=50)])
    guardian_email = StringField("Email (prind)", validators=[Optional(), Email(), Length(max=255)])
    guardian_address = StringField("Adresa (prind)", validators=[Optional(), Length(max=255)])
    guardian_signature = StringField("Firma (shkruaj emrin e plotë)", validators=[Optional(), Length(max=150)])
    guardian_consent_date = DateField("Data", validators=[Optional()], format="%Y-%m-%d")

    # --- Rregullat & Deklarata finale ---
    rules_accepted = HiddenField("rules_accepted", validators=[DataRequired()])
    accepted_info_accurate = BooleanField("Informacioni i dhënë është i saktë", validators=[DataRequired()])
    accepted_rules = BooleanField("Do të respektoj rregullat e kampit dhe drejtuesit", validators=[DataRequired()])
    accepted_safety_notice = BooleanField(
        "Kuptoj se organizatorët do të bëjnë maksimumin për sigurinë", validators=[DataRequired()])
    accepted_media_release = BooleanField(
        "Pranoj fotografimin dhe filmimin për promovim në rrjete sociale", validators=[DataRequired()])
    accepted_privacy_policy = BooleanField("Pajtohem me politikën e privatësisë", validators=[DataRequired()])

    def validate_rules_accepted(self, field):
        if field.data != "yes":
            raise ValidationError("Duhet të lexosh dhe pranosh rregullat e kampit.")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators=extra_validators)
        if not ok:
            return False

        # Nëse < 18 vjeç, kërkohen fushat e prindit/kujdestarit
        from datetime import date
        today = date.today()
        bd = self.birth_date.data
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        self._computed_age = age

        if age < 18:
            required_guardian_fields = [
                self.guardian_name, self.guardian_phone, self.guardian_email,
                self.guardian_signature, self.guardian_consent_date,
            ]
            missing = [f for f in required_guardian_fields if not f.data]
            if missing:
                for f in missing:
                    f.errors.append("Kërkohet për pjesëmarrës nën 18 vjeç.")
                return False

        if self.has_allergies.data == "po" and not self.allergies_description.data:
            self.allergies_description.errors.append("Përshkruaj alergjinë.")
            return False

        if self.takes_medication.data == "po" and not self.medication_name.data:
            self.medication_name.errors.append("Specifiko medikamentin.")
            return False

        return True