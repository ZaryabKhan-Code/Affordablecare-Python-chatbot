from flask import *
import pdfkit
from datetime import datetime
from model.oauth import *
import uuid
import PyPDF2
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import ssl


consent_form = Blueprint('consent_form',__name__)
 # path_wkhtmltopdf = 'wkhtmltopdf/bin/wkhtmltopdf.exe'
# config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)


username = 'info@mail2.affordablecare.ai'
password = '^h]RQ,Zuh0.E'

smtp_server = 'mail2.affordablecare.ai'
smtp_port = 465

@consent_form.route('/generate_pdf_consent_1', methods=['POST'])
def generate_pdf_1():
    try:
        data = request.get_json() 
        primary_writing_agent = data.get('agent_name', 'Default Writing Agent')
        agent_national_number = data.get('agent_npn', 'Default Agent National Number')
        agent_phone = data.get('agent_phone', 'Default Agent Phone')
        agent_email = data.get('agent_support_email', 'Default Agent Email')
        agency_national_number = data.get('agency_npn', 'Default Agency National Number')
        owner_agency = data.get('owner_agency', 'Default Owner Agency')
        agency_phone = data.get('agency_phone', 'Default Agency Phone')
        agency_email = data.get('agency_support_email', 'Default Agency Email')
        primary_household_first_name = data.get('first_name')
        primary_household_last_name = data.get('last_name')
        primary_household_phone = data.get('cell_phone', 'Default Primary Household Phone')
        primary_household_email = data.get('email_address', 'Default Primary Household Email')
        Signature = data.get('signature', 'Default Primary Household Email')
        primary_household_name = f"{primary_household_first_name} {primary_household_last_name}"
        dob = data.get('your_birthday', 'Default Primary Household DOB')
        agent_company_logo = data.get('agent_company_logo')
        agency_name = data.get('agent_company_name')
        
        formatted_date = datetime.now().strftime("%A, %d %B %Y %H:%M:%S")
        
        rendered_template = render_template(
            'consent_1.html',
            primary_writing_agent=primary_writing_agent,
            agent_national_number=agent_national_number,
            agent_phone=agent_phone,
            agent_email=agent_email,
            agency_national_number=agency_national_number,
            owner_agency=owner_agency,
            agency_phone=agency_phone,
            agency_email=agency_email,
            primary_household_name=primary_household_name,
            primary_household_phone=primary_household_phone,
            primary_household_email=primary_household_email,
            date=formatted_date,
            dob=dob,
            agent_company_logo=agent_company_logo,
            image_path=Signature,
            agency_name=agency_name
        )
        pdf = pdfkit.from_string(rendered_template, False, configuration=config, options={"enable-local-file-access": ""})
        random_uuid = str(uuid.uuid4())

        uuid_10 = random_uuid[:10]

        new_pdf = PDF(UUID=uuid_10,content=pdf, extension='pdf', consenttype='1', primaryholderemail=primary_household_email,date=formatted_date,data=data)
        db.session.add(new_pdf)
        db.session.commit()
                
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        agent_email = data.get('agent_support_email','')
        agent_name = data.get('agent_name','')
        agent_npn = data.get('agent_npn','')
        agent_website = data.get('agent_website_url','')

        msg = MIMEMultipart()
        msg['From'] = "support@affordablecare.ai"
        msg['To'] = primary_household_email
        msg['Subject'] = 'Confirmation of Your ACA Marketplace Search Permission'
        html_content = render_template('email_template_1.html',first_name=first_name,last_name=last_name,agent_email=agent_email,agent_name=agent_name,agent_npn=agent_npn,agent_website=agent_website)
        msg.attach(MIMEText(html_content, 'html'))

        pdf_attachment = MIMEApplication(pdf, _subtype="pdf")
        pdf_attachment.add_header('content-disposition', 'attachment', filename=f'{first_name} {last_name}_affordablecareai_consent_1.pdf')
        msg.attach(pdf_attachment)

        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.options |= ssl.OP_NO_TLSv1 
        context.options |= ssl.OP_NO_TLSv1_1


        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(username, password)
        server.sendmail(username, primary_household_email, msg.as_string())
        server.quit()
        
        base_url = request.url_root  

        pdf_link = f'{base_url}get_user_pdf/{primary_household_email}/1/{uuid_10}' 

        return jsonify({"pdf_link": pdf_link})
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500


@consent_form.route('/generate_pdf_consent_2', methods=['POST'])
def generate_pdf_2():
    try:
        form_data = request.get_json()
        
        first_name = form_data.get('first_name', '')
        lowercase_first_name = first_name.lower()
        print(lowercase_first_name)
        print(form_data.get('cell_phone'))
        
        formatted_date = datetime.now().strftime("%A, %d %B %Y %H:%M:%S")
        print(formatted_date)
        other_dependent_names = form_data.get('other_dependent_names_&_gender')
        rendered_template = render_template(
            'consent_2.html',
            form_data=form_data,
            current_date=formatted_date,
            other_dependent_names=other_dependent_names,
            image_path=form_data.get('signature', '')
        )
        text = str(form_data.get('cell_phone'))
        last_4_digits = text[-4:]
        combine = f'{lowercase_first_name}{last_4_digits}'
        pdf = io.BytesIO(pdfkit.from_string(rendered_template, False, configuration=config, options={"enable-local-file-access": ""}))
        pdf_with_password = add_password_to_pdf(pdf.getvalue(), combine)

        if form_data.get('is_your_mailing_address_same', '').lower() == 'no':
            email = form_data.get('your_mailing_address', '')
        elif form_data.get('email_address', '') != '':
            email = form_data.get('email_address', '')
        
        random_uuid = str(uuid.uuid4())
        uuid_10 = random_uuid[:10]
        
        new_pdf = PDF(
            content=pdf_with_password,
            extension='pdf',
            consenttype='2',
            primaryholderemail=email,
            date=formatted_date,
            data=form_data,
            UUID=uuid_10
        )        
        db.session.add(new_pdf)
        db.session.commit()
        
        first_name=form_data.get('first_name', '')
        last_name=form_data.get('last_name', '')
        agent_email = form_data.get('agent_support_email','')
        agent_name = form_data.get('agent_name','')
        agent_npn = form_data.get('agent_npn','')
        agent_website = form_data.get('agent_website_url','')

        msg = MIMEMultipart()
        msg['From'] = "support@affordablecare.ai"
        msg['To'] = email
        msg['Subject'] = 'ACA Insurance Marketplace Search and Enrollment Permission Consent'
        html_content = render_template('email_template_2.html',first_name=first_name,last_name=last_name,agent_email=agent_email,agent_name=agent_name,agent_npn=agent_npn,agent_website=agent_website)
        msg.attach(MIMEText(html_content, 'html'))

        pdf_attachment = MIMEApplication(pdf_with_password, _subtype="pdf")
        pdf_attachment.add_header('content-disposition', 'attachment', filename=f'{first_name} {last_name}_affordablecareai_consent_2.pdf')
        msg.attach(pdf_attachment)

        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.options |= ssl.OP_NO_TLSv1 
        context.options |= ssl.OP_NO_TLSv1_1


        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(username, password)
        server.sendmail(username, email, msg.as_string())
        server.quit()
        
        base_url = request.url_root  

        pdf_link = f'{base_url}get_user_pdf/{email}/2/{uuid_10}' 

        return jsonify({"pdf_link": pdf_link})
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    
    
@consent_form.route('/get_user_pdf/<email>/<consent>/<uuid>', methods=['GET'])
def get_pdf_by_email_and_consent(email, consent,uuid):
    try:
        pdf_entry = PDF.query.filter_by(primaryholderemail=email, consenttype=consent,UUID=uuid).first()
        if pdf_entry:
            response = Response(pdf_entry.content, content_type='application/pdf')
            response.headers['Content-Disposition'] = f'inline; filename={email}_affordablecareai_consent_{consent}.pdf'
            return response
        else:
            return jsonify({"error": "PDF not found"}), 404
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500



def add_password_to_pdf(pdf_bytes, password):
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    pdf_writer = PyPDF2.PdfWriter()

    for page in pdf_reader.pages:
        pdf_writer.add_page(page)

    pdf_writer.encrypt(password)

    pdf_with_password = io.BytesIO()
    pdf_writer.write(pdf_with_password)
    
    return pdf_with_password.getvalue()

