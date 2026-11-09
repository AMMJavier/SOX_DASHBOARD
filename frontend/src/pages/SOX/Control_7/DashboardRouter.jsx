import AdminDashboard from "./AdminDashboard";
import ManagerDashboard from "./ManagerDashboard";

export default function DashboardRouter(){

    const user = JSON.parse(localStorage.getItem("soxUser"));

    if(!user){
        return null;
    }


    const rol = user.rol?.toLowerCase();


    if(
        rol === "root" ||
        rol === "administrador" ||
        rol === "desarrollador"
    ){
        return <AdminDashboard />;
    }


    if(rol === "gerencial"){
        return <ManagerDashboard />;
    }


    return <ManagerDashboard />;

}