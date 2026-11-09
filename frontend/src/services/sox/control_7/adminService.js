import { api } from "../../api";


export async function getAdminValidations(){

    const response = await api.get(
        "/sox/admin/validations"
    );

    return response.data;

}